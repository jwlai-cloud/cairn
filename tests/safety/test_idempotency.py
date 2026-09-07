"""Duplicate action requests replay; they never double-apply."""

import pytest

from app.domain.models import ActionRequest, ActionType
from app.tools.action_tools import ActionRejected


async def _approved(run):
    run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    return run.approval


async def test_duplicate_action_replays_without_a_new_side_effect(analysed_run):
    approval = await _approved(analysed_run)
    first = analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    before = dict(analysed_run.gateway.simulation_store)

    # Same approval, same keys, submitted again (a retry, a double click, a redelivery).
    analysed_run.approval = approval.model_copy(update={"status": approval.status})
    second = analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])

    assert [r.artefact_ref for r in first] == [r.artefact_ref for r in second]
    assert all(r.replayed for r in second)
    assert analysed_run.gateway.simulation_store == before, "a replay must not create a second artefact"
    assert len(analysed_run.gateway.records) == len(first)


async def test_same_key_with_a_different_payload_is_a_conflict(analysed_run):
    approval = await _approved(analysed_run)
    analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
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
        analysed_run.gateway.execute(request, approval=approval, actor_roles=["SHIFT_SUPERVISOR"], evidence=[])
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
        analysed_run.gateway.execute(request, approval=approval, actor_roles=["SHIFT_SUPERVISOR"], evidence=[])
    assert excinfo.value.code == "VERSION_CONFLICT"


async def test_every_action_is_simulation_only(analysed_run):
    await _approved(analysed_run)
    records = analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    assert records
    for record in records:
        assert record.simulated is True
        assert record.artefact_ref.startswith("SIM-")
        assert "simulation" in record.artefact["system"].lower()


async def test_an_unknown_outcome_blocks_a_retry_even_when_the_approval_expired(analysed_run):
    """The reconciliation guard must outrank approval validation.

    Answering APPROVAL_EXPIRED here would tell the operator to fetch a fresh approval
    for an action that may already have applied.
    """
    from datetime import timedelta

    from app.domain.models import utcnow

    approval = await _approved(analysed_run)
    analysed_run.simulate_action_timeout(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.approval = approval.model_copy(update={"expires_at": utcnow() - timedelta(seconds=1)})

    with pytest.raises(ActionRejected) as excinfo:
        analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    assert excinfo.value.code == "RECONCILIATION_REQUIRED"


async def test_any_transport_failure_resolves_the_claim_rather_than_escaping(analysed_run):
    """An escaping exception would strand the idempotency key as IN_PROGRESS forever."""
    from app.domain.models import ActionStatus

    await _approved(analysed_run)

    def broken(_request):
        raise ConnectionResetError("connection reset by the simulated work-order system")

    records = analysed_run.execute_approved_actions(
        actor_id="u", actor_roles=["SHIFT_SUPERVISOR"], transport=broken
    )
    assert records and all(r.status is ActionStatus.UNKNOWN for r in records)
    assert all("ConnectionResetError" in r.message for r in records)
    assert analysed_run.gateway.simulation_store == {}
    # And the stranded claim is reconcilable rather than stuck.
    resolved = analysed_run.reconcile_action(records[0].action_id, applied=False, actor_id="u")
    assert resolved.status is ActionStatus.FAILED


async def test_reconciliation_passes_through_the_declared_intermediate_state(analysed_run):
    """05 5.7 declares UNKNOWN -> RECONCILING -> SUCCEEDED/FAILED."""
    await _approved(analysed_run)
    records = analysed_run.simulate_action_timeout(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.reconcile_action(records[0].action_id, applied=True, actor_id="u")
    stages = [e.stage for e in analysed_run.view().audit]
    assert "ACTION_UNKNOWN" in stages
    assert "ACTION_RECONCILING" in stages
    assert stages.index("ACTION_RECONCILING") > stages.index("ACTION_UNKNOWN")
    assert "ACTION_RECONCILED" in stages


async def test_the_timeout_override_does_not_leak_onto_the_shared_gateway(analysed_run):
    """A per-call override; a concurrent action must not be dragged through it."""
    default = analysed_run.gateway.transport
    await _approved(analysed_run)
    analysed_run.simulate_action_timeout(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    assert analysed_run.gateway.transport is default
