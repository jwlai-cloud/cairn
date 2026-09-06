"""Duplicate action requests replay; they never double-apply."""

import pytest

from app.domain.models import ActionRequest, ActionType
from app.tools.action_tools import ActionRejected


async def _approved(run):
    run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_BOSS"])
    run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_BOSS")
    return run.approval


async def test_duplicate_action_replays_without_a_new_side_effect(analysed_run):
    approval = await _approved(analysed_run)
    first = analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_BOSS"])
    before = dict(analysed_run.gateway.simulation_store)

    # Same approval, same keys, submitted again (a retry, a double click, a redelivery).
    analysed_run.approval = approval.model_copy(update={"status": approval.status})
    second = analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_BOSS"])

    assert [r.artefact_ref for r in first] == [r.artefact_ref for r in second]
    assert all(r.replayed for r in second)
    assert analysed_run.gateway.simulation_store == before, "a replay must not create a second artefact"
    assert len(analysed_run.gateway.records) == len(first)


async def test_same_key_with_a_different_payload_is_a_conflict(analysed_run):
    approval = await _approved(analysed_run)
    analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_BOSS"])
    key = analysed_run.gateway.records[0].idempotency_key
    action_type = analysed_run.gateway.records[0].action_type

    request = ActionRequest(
        action_id="act_conflict",
        action_type=action_type,
        approval_token=approval.approval_token,
        idempotency_key=key,
        actor_id="u",
        site_id="site_pilbara_01",
        policy_decision_id=None,
        correlation_id="corr_compound_disruption_v1",
        expected_version=approval.scenario_version,
        reason="different payload, same key",
        payload={"instruction": "something else entirely"},
    )
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.gateway.execute(request, approval=approval, actor_roles=["SHIFT_BOSS"], evidence=[])
    assert excinfo.value.code == "IDEMPOTENCY_CONFLICT"


async def test_stale_plan_version_is_a_version_conflict(analysed_run):
    approval = await _approved(analysed_run)
    request = ActionRequest(
        action_id="act_old_version",
        action_type=ActionType.CREATE_WORK_ORDER,
        approval_token=approval.approval_token,
        idempotency_key="act:v1:old-version",
        actor_id="u",
        site_id="site_pilbara_01",
        policy_decision_id=None,
        correlation_id="corr_compound_disruption_v1",
        expected_version=approval.scenario_version + 1,
        reason="plan moved on",
        payload={},
    )
    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.gateway.execute(request, approval=approval, actor_roles=["SHIFT_BOSS"], evidence=[])
    assert excinfo.value.code == "VERSION_CONFLICT"


async def test_every_action_is_simulation_only(analysed_run):
    await _approved(analysed_run)
    records = analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_BOSS"])
    assert records
    for record in records:
        assert record.simulated is True
        assert record.artefact_ref.startswith("SIM-")
        assert "simulation" in record.artefact["system"].lower()
