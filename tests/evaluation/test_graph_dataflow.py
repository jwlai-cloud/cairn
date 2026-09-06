"""The graph's edges must carry data, not just execution order.

These are the tests that fail if the nodes stop reading each other. Before the reducer
rewrite, every one of them failed: the planner returned the same three options no matter
what the specialists said, which made the DAG decorative.
"""

import pytest

from app.agents import reducers
from app.agents.context import GraphContext
from app.agents.fixture_model import UpstreamParseError, parse_upstream
from app.agents.graph import run_graph
from app.domain.models import Severity
from app.integrations.fixture_source import FixtureSource

PROMPT = "Compound disruption on Shift A at North Pit."


def context_for(*, drop: set[str] = frozenset()) -> GraphContext:
    source = FixtureSource()
    events = tuple(e for e in source.events() if e.event_type.value not in drop)
    kept = {eid for e in events for eid in e.evidence_ids}
    return GraphContext(
        events=events,
        evidence=tuple(e for e in source.evidence() if e.evidence_id in kept),
        site=source.site_model(),
        baseline_kpi=source.baseline_kpi(),
    )


async def plan_for(ctx: GraphContext):
    return (await run_graph(PROMPT, ctx)).outputs["scenario_planner"]


# ------------------------------------------------------- the headline regression


async def test_deleting_every_hazard_changes_the_plan(monkeypatch):
    """The test that used to fail. Remove the risk agent's findings and the plan must move."""
    ctx = context_for()
    before = await plan_for(ctx)

    original = reducers.risk

    def no_hazards(c):
        assessment = original(c)
        assessment.findings = []
        assessment.headline = "No hazards identified from the available evidence"
        return assessment

    monkeypatch.setattr(reducers, "risk", no_hazards)
    after = await plan_for(ctx)

    # A binding control is the only thing that closes a route. With no findings there is
    # no binding control, so nothing may be closed.
    assert [o.closed_route_ids for o in before.options] != [o.closed_route_ids for o in after.options]
    assert all(o.closed_route_ids == [] for o in after.options)
    assert all(o.safety_risk_level is Severity.LOW for o in after.options)
    assert before.would_change_if != after.would_change_if


async def test_raising_a_hazard_severity_flips_the_recommendation(monkeypatch):
    ctx = context_for()
    assert (await plan_for(ctx)).recommended_scenario_id == "scn_recover_tonnes"

    original = reducers.risk

    def congestion_is_severe(c):
        assessment = original(c)
        for finding in assessment.findings:
            if finding.risk_id == "risk_north_ramp_congestion":
                finding.severity = Severity.HIGH
        return assessment

    monkeypatch.setattr(reducers, "risk", congestion_is_severe)
    after = await plan_for(ctx)
    assert after.recommended_scenario_id == "scn_protect_safety", (
        "the option that leaves a HIGH residual hazard must stop winning"
    )


# ------------------------------------------------- events actually drive the plan


async def test_losing_a_second_truck_reduces_every_option(monkeypatch):
    baseline = await plan_for(context_for())
    ctx = context_for()
    monkeypatch.setattr(type(ctx), "trucks_lost", property(lambda self: 2))
    reduced = await plan_for(ctx)
    for before, after in zip(baseline.options, reduced.options):
        assert after.impacts.estimated_tonnes_delta < before.impacts.estimated_tonnes_delta


async def test_removing_the_maintenance_constraint_shortens_the_preserve_option():
    full = await plan_for(context_for())
    without = await plan_for(context_for(drop={"MAINTENANCE_CONSTRAINT"}))
    before = next(o for o in full.options if o.key == "preserve_equipment")
    after = next(o for o in without.options if o.key == "preserve_equipment")
    assert before.impacts.estimated_recovery_minutes == 140
    assert after.impacts.estimated_recovery_minutes < before.impacts.estimated_recovery_minutes


async def test_removing_the_weather_alert_removes_every_route_closure():
    without = await plan_for(context_for(drop={"WEATHER_ALERT"}))
    assert all(o.closed_route_ids == [] for o in without.options)
    assert all(o.safety_risk_level is not Severity.HIGH for o in without.options)


async def test_an_option_whose_constraint_is_unestablished_is_dropped():
    """recover_tonnes needs a stockpile buffer. With no production constraint, it is not offered."""
    without = await plan_for(context_for(drop={"PRODUCTION_CONSTRAINT"}))
    keys = {o.key for o in without.options}
    assert "recover_tonnes" not in keys
    assert keys == {"protect_safety", "preserve_equipment"}
    assert any("not feasible" in u for u in without.unknowns)


async def test_fewer_events_produce_a_smaller_incident():
    full = (await run_graph(PROMPT, context_for())).outputs["situation"]
    partial = (await run_graph(PROMPT, context_for(drop={"WEATHER_ALERT", "PRODUCTION_CONSTRAINT"}))).outputs[
        "situation"
    ]
    assert len(partial.correlated_event_ids) == 3
    assert len(full.correlated_event_ids) == 5
    assert partial.narrative != full.narrative
    assert partial.headline != full.headline


async def test_confidence_falls_as_unknowns_rise():
    """Uncertainty has to cost something, or confidence is decoration."""
    full = await plan_for(context_for())
    # Dropping the weather alert removes the conflicting-source unknown.
    fewer = await plan_for(context_for(drop={"WEATHER_ALERT"}))
    assert fewer.confidence > full.confidence


# ----------------------------------------------------------- transport integrity


def test_parse_upstream_reads_the_strands_graph_prompt():
    messages = [
        {
            "role": "user",
            "content": [
                {"text": "Original Task: do the thing"},
                {"text": "\nInputs from previous nodes:"},
                {"text": "\nFrom situation:"},
                {"text": '  - Agent: {"headline":"A","confidence":0.5}'},
                {"text": "\nFrom risk:"},
                {"text": '  - Agent: {"headline":"B","confidence":0.9}'},
            ],
        }
    ]
    parsed = parse_upstream(messages)
    assert set(parsed) == {"situation", "risk"}
    assert parsed["risk"]["confidence"] == 0.9


def test_a_node_that_loses_its_upstream_fails_loudly():
    """A silent fallback is how a graph starts looking connected while nodes ignore each other."""
    from app.agents.fixture_model import FixtureModel

    model = FixtureModel(lambda _u: None, node_id="scenario_planner", requires=("situation", "risk"))
    with pytest.raises(UpstreamParseError) as excinfo:
        model._resolve([{"role": "user", "content": [{"text": "Original Task: nothing upstream"}]}])
    assert "situation" in str(excinfo.value)


async def test_the_planner_really_receives_all_four_specialists():
    seen: dict = {}
    ctx = context_for()
    original = reducers.scenario_planner

    def capture(c, **kwargs):
        seen.update(kwargs)
        return original(c, **kwargs)

    import app.agents.reducers as module

    object.__setattr__(module, "scenario_planner", capture)
    try:
        await plan_for(ctx)
    finally:
        object.__setattr__(module, "scenario_planner", original)

    assert set(seen) == {"situation_summary", "reliability_set", "operations_set", "risk_assessment"}
    assert seen["risk_assessment"].findings, "the planner must receive the risk agent's real findings"
    assert seen["situation_summary"].correlated_event_ids
