"""The contract must constrain values, not just types, in either mode.

Every defect the Bedrock run exposed was hidden the same way: the fixture always wrote
the right value, so nothing asserted that the *contract* required it. `key` was a `str`
with its legal values in a comment. `required_approvals` was `list[str]`, so a model
could invent a role the approval service cannot resolve. `recommended_scenario_id` was a
`str`, so it could point at nothing.

These tests assert the schema itself, so they hold for any provider without needing
credentials or a network. The Bedrock half of the claim is exercised by
`app/agents/smoke.py`, which runs the real graph when credentials exist.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.models import Role, ScenarioKey, ScenarioSet
from app.integrations.fixture_source import FixtureSource


@pytest.fixture(scope="module")
def planned() -> ScenarioSet:
    """The planner's output from a real fixture-mode graph run.

    Built by running the graph rather than by hand, so the sample is whatever the
    application actually produces. Fixture mode is deterministic and takes 232ms.
    """
    import asyncio

    from app.agents.context import GraphContext
    from app.agents.graph import run_graph

    src = FixtureSource()
    ctx = GraphContext(
        tuple(src.events()), tuple(src.evidence()), src.site_model(), src.baseline_kpi()
    )
    res = asyncio.run(run_graph("Compound disruption on Shift A at North Pit.", ctx))
    return res.outputs["scenario_planner"]


def test_a_scenario_key_outside_the_three_is_rejected(planned):
    """Nova Lite returned option_1. The old `str` field accepted it."""
    base = planned
    payload = base.model_dump(by_alias=True)
    payload["options"][0]["key"] = "option_1"
    with pytest.raises(ValidationError, match="key"):
        ScenarioSet.model_validate(payload)


def test_an_approval_role_the_policy_cannot_resolve_is_rejected(planned):
    """Nova Lite returned operations_manager, which is plausible and unresolvable."""
    base = planned
    payload = base.model_dump(by_alias=True)
    payload["options"][0]["requiredApprovals"] = ["operations_manager"]
    with pytest.raises(ValidationError, match="requiredApprovals"):
        ScenarioSet.model_validate(payload)


def test_a_recommendation_pointing_at_no_option_is_rejected(planned):
    """Nova Lite returned scenario_id_1 while its options were opt_1 to opt_3."""
    base = planned
    payload = base.model_dump(by_alias=True)
    payload["recommendedScenarioId"] = "scenario_id_1"
    with pytest.raises(ValidationError, match="not one of"):
        ScenarioSet.model_validate(payload)


def test_the_constrained_values_reach_the_schema_the_model_is_shown():
    """Strands builds a forced tool call from this schema, so the model sees the enums.

    A constraint the schema does not carry is a constraint the model is never told about,
    which is how the loose fields survived: the prompt did not name the legal values
    either.
    """
    schema = ScenarioSet.model_json_schema(by_alias=True)
    text = str(schema)
    for key in ScenarioKey:
        assert key.value in text, f"{key.value} missing from the generated schema"
    for role in Role:
        assert role.value in text, f"{role.value} missing from the generated schema"
    assert "recovers tonnes" in text.lower(), "the tonnes sign convention is not in the schema"


def test_the_fixture_satisfies_every_constraint_it_now_carries(planned):
    """The fixture passing is not evidence the contract is tight - it is why it was loose."""
    got = planned
    assert {o.key for o in got.options} == set(ScenarioKey)
    assert got.recommended_scenario_id in {o.scenario_id for o in got.options}
    for o in got.options:
        assert o.required_approvals, "every option must name an approver"
        assert all(isinstance(r, Role) for r in o.required_approvals)
        assert o.impacts.estimated_tonnes_delta > 0, (
            "the convention is tonnes recovered against doing nothing, so positive"
        )
