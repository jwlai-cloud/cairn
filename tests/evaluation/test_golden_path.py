"""The golden path from docs/architecture/06 6.4 and 08 8.5."""

from app.domain.models import ActionType, ApprovalStatus, RunStatus


async def test_five_signals_become_one_incident(analysed_run):
    view = analysed_run.view()
    assert len(view.events) == 5
    assert view.incident is not None
    assert len(view.incident.event_ids) == 5, "five signals, one incident, not five alerts"
    assert "asset_primary_crusher_01" in view.incident.affected_asset_ids
    assert "asset_truck_204" in view.incident.affected_asset_ids
    assert view.incident.weather_window_minutes == 42


async def test_all_five_graph_nodes_complete(analysed_run):
    agents = [n for n in analysed_run.view().nodes if n.kind == "strands-agent"]
    assert len(agents) == 5
    assert all(n.status.value == "COMPLETED" for n in agents)
    assert all(n.confidence is not None and n.evidence_ids for n in agents)


async def test_three_options_cover_the_three_strategies(analysed_run):
    keys = {o.key for o in analysed_run.scenarios}
    assert keys == {"protect_safety", "recover_tonnes", "preserve_equipment"}
    protect = next(o for o in analysed_run.scenarios if o.key == "protect_safety")
    recover = next(o for o in analysed_run.scenarios if o.key == "recover_tonnes")
    preserve = next(o for o in analysed_run.scenarios if o.key == "preserve_equipment")
    assert recover.impacts.estimated_tonnes_delta > protect.impacts.estimated_tonnes_delta
    assert protect.safety_risk_level.value == "LOW"
    assert preserve.impacts.estimated_throughput_delta < recover.impacts.estimated_throughput_delta


async def test_every_option_respects_the_standing_ramp_closure_control(analysed_run):
    for option in analysed_run.scenarios:
        assert "route_east_ramp" in option.closed_route_ids, (
            "the ramp closure is a standing geotechnical control; no option may trade it away"
        )


async def test_selecting_a_scenario_changes_the_scene_read_model(analysed_run):
    analysed_run.select_scenario("scn_preserve_equipment")
    site = analysed_run.view().site
    closed = {r.route_id for r in site.routes if not r.open}
    assert closed == {"route_east_ramp"}
    failed = {a.asset_id for a in site.assets if a.state.value == "FAILED"}
    assert {"asset_primary_crusher_01", "asset_truck_204"} <= failed


async def test_full_chain_reaches_a_verified_outcome(analysed_run):
    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    assert analysed_run.approval.status is ApprovalStatus.PENDING
    analysed_run.decide_approval(approve=True, approver_id="user_shift_supervisor_01", approver_role="SHIFT_SUPERVISOR")
    records = analysed_run.execute_approved_actions(
        actor_id="user_shift_supervisor_01", actor_roles=["SHIFT_SUPERVISOR"]
    )
    assert {r.action_type for r in records} == {
        ActionType.PUBLISH_SHIFT_INSTRUCTION,
        ActionType.CREATE_WORK_ORDER,
    }
    outcome = analysed_run.verify_outcome()
    assert outcome.verified and outcome.action_ids
    assert outcome.unresolved_items, "an honest outcome names what is still open"
    assert analysed_run.view().status is RunStatus.COMPLETED


async def test_audit_reconstructs_the_whole_chain(analysed_run):
    analysed_run.attempt_and_ignore = None
    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.verify_outcome()

    stages = [e.stage for e in analysed_run.view().audit]
    for required in (
        "EVENT_INGESTED", "GRAPH_STARTED", "AGENT_FINDING", "SCENARIOS_PROPOSED",
        "POLICY_DECISION", "APPROVAL_REQUESTED", "APPROVAL_GRANTED",
        "ACTION_EXECUTED", "OUTCOME_VERIFIED",
    ):
        assert required in stages, f"audit chain is missing {required}"
    seqs = [e.seq for e in analysed_run.view().audit]
    assert seqs == sorted(seqs) == list(range(1, len(seqs) + 1)), "ledger must be append-only and ordered"


async def test_verified_outcome_does_not_pretend_the_disruption_is_over(analysed_run):
    """A projected recovery must not silently restore the truck count or clear risks."""
    analysed_run.request_approval("scn_recover_tonnes", actor_roles=["SHIFT_SUPERVISOR"])
    analysed_run.decide_approval(approve=True, approver_id="u", approver_role="SHIFT_SUPERVISOR")
    analysed_run.execute_approved_actions(actor_id="u", actor_roles=["SHIFT_SUPERVISOR"])
    outcome = analysed_run.verify_outcome()

    kpi = analysed_run.view().kpi
    baseline = analysed_run.source.baseline_kpi()
    assert kpi.active_trucks == baseline.active_trucks - 1, "Truck 204 is still unavailable"
    assert kpi.weather_window_minutes == 42, "the weather window has not disappeared"
    assert kpi.unresolved_risks == len(outcome.residual_risks) > 0
    assert kpi.tonnes_moved > baseline.tonnes_moved
