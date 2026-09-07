"""Approval is a scoped, expiring, single-use authorisation, not a boolean."""

from datetime import timedelta

import pytest

from app.domain.models import ActionType, ApprovalStatus, utcnow
from app.tools.action_tools import ActionRejected


async def test_action_without_approval_is_refused(analysed_run):
    analysed_run.select_scenario("scn_recover_tonnes")
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    assert excinfo.value.code == "APPROVAL_REQUIRED"


async def test_pending_approval_cannot_be_consumed(analysed_run):
    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    assert analysed_run.approval.status is ApprovalStatus.PENDING
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    assert excinfo.value.code in ("APPROVAL_REQUIRED", "APPROVAL_INVALID")
    assert not analysed_run.gateway.records


async def test_rejected_approval_blocks_the_action(analysed_run):
    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.decide_approval(approve=False, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    assert analysed_run.approval.status is ApprovalStatus.REJECTED
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    assert excinfo.value.code == "APPROVAL_REJECTED"


async def test_expired_approval_fails_closed(analysed_run):
    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    analysed_run.approval = analysed_run.approval.model_copy(
        update={"expires_at": utcnow() - timedelta(seconds=1)}
    )
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    assert excinfo.value.code == "APPROVAL_EXPIRED"
    assert not analysed_run.gateway.records


async def test_approver_must_hold_a_required_role(analysed_run):
    analysed_run.request_approval("scn_preserve_equipment", actor_roles=["SHIFT_SUPERVISOR", "MAINTENANCE_PLANNER"])
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.decide_approval(approve=True, approver_id="u", approver_role="VISITOR")
    assert excinfo.value.code == "APPROVAL_INVALID"


async def test_changing_the_plan_supersedes_the_approval(analysed_run):
    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    analysed_run.select_scenario("scn_protect_safety")
    assert analysed_run.approval.status is ApprovalStatus.SUPERSEDED
    with pytest.raises(ActionRejected):
        analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])


async def test_forged_token_is_refused(analysed_run):
    from app.domain.models import ActionRequest

    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    request = ActionRequest(
        action_id="act_forged",
        action_type=ActionType.CREATE_WORK_ORDER,
        approval_token="apt_definitely_not_the_real_token",
        idempotency_key="act:v1:forged",
        actor_id="u",
        site_id="site_pilbara_01",
        policy_decision_id=None,
        correlation_id="corr_compound_disruption_v1",
        expected_version=1,
        reason="forged",
        payload={},
    )
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.gateway.execute(
            request, approval=analysed_run.approval, actor_roles=["SHIFT_SUPERVISOR"], evidence=[]
        )
    assert excinfo.value.code == "APPROVAL_INVALID"


async def test_action_outside_approved_scope_is_refused(analysed_run):
    from app.domain.models import ActionRequest

    analysed_run.request_approval("scn_protect_safety", actor_roles=["SHIFT_SUPERVISOR"])
    approval = analysed_run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    assert ActionType.CREATE_WORK_ORDER not in approval.requested_action_types
    request = ActionRequest(
        action_id="act_scope",
        action_type=ActionType.CREATE_WORK_ORDER,
        approval_token=approval.approval_token,
        idempotency_key="act:v1:scope",
        actor_id="u",
        site_id="site_pilbara_01",
        policy_decision_id=None,
        correlation_id="corr_compound_disruption_v1",
        expected_version=approval.scenario_version,
        reason="out of scope",
        payload={},
    )
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.gateway.execute(request, approval=approval, actor_roles=["SHIFT_SUPERVISOR"], evidence=[])
    assert excinfo.value.code == "APPROVAL_OUT_OF_SCOPE"
