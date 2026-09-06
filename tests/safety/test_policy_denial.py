"""Prohibited actions are denied deterministically, with no model in the path."""

import pytest

from app.domain.models import ActionType, PolicyEffect
from app.domain.run_service import Run
from app.policy.decisions import PolicyService, is_prohibited
from app.tools.action_tools import ActionRejected

PROHIBITED = [
    ActionType.OVERRIDE_SAFETY_INTERLOCK,
    ActionType.APPROVE_BLAST_PERMIT,
    ActionType.CHANGE_ISOLATION_STATE,
    ActionType.SET_CRUSHER_CONTROL_SETPOINT,
]


@pytest.mark.parametrize("action_type", PROHIBITED)
def test_tier_four_is_denied_for_every_role(action_type):
    policy = PolicyService()
    for roles in (["SHIFT_BOSS"], ["HSE_LEAD"], ["SHIFT_BOSS", "MAINTENANCE_PLANNER", "HSE_LEAD"], []):
        decision = policy.evaluate(
            action_type=action_type, actor_roles=roles, correlation_id="c", decision_id="d"
        )
        assert decision.effect is PolicyEffect.DENY
        assert decision.tier == 4
    assert is_prohibited(action_type)


def test_policy_denial_does_not_touch_the_agent_layer(monkeypatch):
    """If policy called a model, this would raise. It must not."""
    import app.agents.graph as graph

    async def explode(*_a, **_k):  # pragma: no cover - only runs on regression
        raise AssertionError("policy must not invoke the agent graph")

    monkeypatch.setattr(graph, "run_graph", explode)
    decision = PolicyService().evaluate(
        action_type=ActionType.OVERRIDE_SAFETY_INTERLOCK,
        actor_roles=["SHIFT_BOSS"],
        correlation_id="c",
        decision_id="d",
    )
    assert decision.effect is PolicyEffect.DENY


def test_action_missing_from_the_policy_table_fails_closed(monkeypatch):
    """A new action type that nobody wrote a rule for must be denied, not allowed."""
    import app.policy.decisions as policy_module

    table = dict(policy_module.RULES)
    table.pop(ActionType.CREATE_WORK_ORDER)
    monkeypatch.setattr(policy_module, "RULES", table)

    decision = PolicyService().evaluate(
        action_type=ActionType.CREATE_WORK_ORDER,
        actor_roles=["SHIFT_BOSS"],
        correlation_id="c",
        decision_id="d",
    )
    assert decision.effect is PolicyEffect.DENY
    assert decision.rule_id == "RULE-FAIL-CLOSED"
    assert decision.tier == 4


def test_role_without_authority_is_denied():
    decision = PolicyService().evaluate(
        action_type=ActionType.CREATE_WORK_ORDER, actor_roles=["VISITOR"], correlation_id="c", decision_id="d"
    )
    assert decision.effect is PolicyEffect.DENY
    assert "SHIFT_BOSS" in decision.required_roles


async def test_prohibited_action_through_the_gateway_is_denied_and_audited(analysed_run):
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.attempt_prohibited_action(
            action_type=ActionType.OVERRIDE_SAFETY_INTERLOCK,
            actor_id="user_shift_boss_01",
            actor_roles=["SHIFT_BOSS", "MAINTENANCE_PLANNER"],
        )
    assert excinfo.value.code == "POLICY_DENIED"
    assert excinfo.value.details["ruleId"] == "RULE-T4-PROHIBITED-INTERLOCK"
    assert not analysed_run.gateway.records, "a denied action must leave no artefact"
    assert any(e.stage == "POLICY_DECISION" for e in analysed_run.ledger.entries)
