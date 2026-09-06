"""Contract tests: the wire shape is the promise, not the implementation."""

from app.domain.models import RunView, ScenarioOption
from app.domain.run_service import Run


def test_fixture_loads_with_expected_shape():
    run = Run()
    site = run.source.site_model()
    trucks = [a for a in site.assets if a.kind == "TRUCK"]
    assert 6 <= len(trucks) <= 10, "demo brief requires six to ten haul trucks"
    assert {a.kind for a in site.assets} >= {"CRUSHER", "PLANT", "STOCKPILE", "WORKSHOP", "WEATHER_ZONE", "BENCH"}
    assert len(site.routes) >= 3
    assert any(r.exposed_to_weather for r in site.routes)


def test_events_are_ordered_and_complete():
    run = Run()
    events = run.source.events()
    assert len(events) == 5
    assert [e.offset_seconds for e in events] == sorted(e.offset_seconds for e in events)
    assert {e.event_type.value for e in events} == {
        "ASSET_DEGRADED", "ASSET_UNAVAILABLE", "WEATHER_ALERT",
        "MAINTENANCE_CONSTRAINT", "PRODUCTION_CONSTRAINT",
    }


def test_crusher_event_is_a_25_percent_drop():
    run = Run()
    crusher = next(e for e in run.source.events() if e.event_id == "evt_crusher_derate")
    nominal = crusher.measurements["nominalCapacityPercent"]
    assert crusher.measurements["capacityPercent"] == nominal * 0.75


def test_weather_window_is_42_minutes():
    run = Run()
    weather = next(e for e in run.source.events() if e.event_type.value == "WEATHER_ALERT")
    assert weather.measurements["minutesToClosure"] == 42


async def test_run_view_serialises_as_camel_case(analysed_run):
    payload = analysed_run.view().model_dump(by_alias=True)
    assert "correlationId" in payload and "correlation_id" not in payload
    assert RunView.model_validate(payload)


async def test_every_scenario_exposes_the_required_decision_fields(analysed_run):
    assert len(analysed_run.scenarios) == 3
    for option in analysed_run.scenarios:
        assert isinstance(option, ScenarioOption)
        assert option.impacts.estimated_tonnes_delta
        assert option.impacts.estimated_recovery_minutes > 0
        assert option.safety_risk_level
        assert option.assumptions and option.unknowns and option.constraints
        assert option.evidence_ids
        assert 0 < option.confidence <= 1
        assert option.required_approvals, "every option must name who has to approve it"


async def test_options_are_meaningfully_different(analysed_run):
    tonnes = {o.impacts.estimated_tonnes_delta for o in analysed_run.scenarios}
    minutes = {o.impacts.estimated_recovery_minutes for o in analysed_run.scenarios}
    throughput = {o.impacts.estimated_throughput_delta for o in analysed_run.scenarios}
    assert len(tonnes) == 3 and len(minutes) == 3 and len(throughput) == 3


async def test_no_chain_of_thought_field_is_exposed(analysed_run):
    payload = analysed_run.view().model_dump(by_alias=True)
    blob = str(payload).lower()
    for banned in ("chain_of_thought", "chainofthought", "reasoning_trace", "scratchpad"):
        assert banned not in blob
