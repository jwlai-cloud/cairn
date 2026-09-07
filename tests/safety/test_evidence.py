"""Stale and conflicting evidence must be surfaced, never silently resolved."""

from app.domain.models import ActionType
from app.policy.decisions import PolicyService


async def test_stale_evidence_is_flagged_not_dropped(analysed_run):
    view = analysed_run.view()
    assert "evd_fleet_telemetry_stale" in view.stale_evidence_ids
    stale = next(e for e in view.evidence if e.evidence_id == "evd_fleet_telemetry_stale")
    assert stale.stale is True
    assert any("STALE EVIDENCE" in n for n in view.notices)
    assert any(e.stage == "EVIDENCE_STALE" for e in view.audit)


async def test_conflicting_sources_are_both_retained(analysed_run):
    view = analysed_run.view()
    ids = {e.evidence_id for e in view.evidence}
    assert {"evd_weather_bom", "evd_weather_onsite"} <= ids, "neither conflicting source may be discarded"
    assert view.conflict_notes and "CONFLICT" in view.conflict_notes[0]
    assert any(e.stage == "EVIDENCE_CONFLICT" for e in view.audit)


async def test_the_conflict_is_carried_into_the_options(analysed_run):
    unknowns = " ".join(u for o in analysed_run.scenarios for u in o.unknowns)
    situation_unknowns = " ".join(analysed_run.outputs["situation"].unknowns)
    assert "42" in situation_unknowns and "55" in situation_unknowns
    assert unknowns, "options must not present a disputed forecast as settled"


def test_all_stale_evidence_blocks_a_tier_three_commit():
    from datetime import datetime, timezone

    from app.domain.models import Evidence

    stale = [
        Evidence(
            evidence_id="evd_x",
            source_system="s",
            source_record_id="r",
            observed_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            freshness_seconds=999,
            reliability=0.2,
            summary="stale",
            stale=True,
        )
    ]
    decision = PolicyService().evaluate(
        action_type=ActionType.CREATE_WORK_ORDER,
        actor_roles=["SHIFT_SUPERVISOR"],
        correlation_id="c",
        decision_id="d",
        evidence=stale,
    )
    assert decision.effect.value == "DENY"
    assert decision.rule_id == "RULE-T3-STALE-EVIDENCE"
