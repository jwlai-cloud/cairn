"""Deterministic policy service.

The model is not the authorization boundary (docs/architecture/04, ADR-003). Nothing
in this module calls an LLM, reads a prompt, or inspects model output. It is a pure
function of action type, actor role, scope and freshness, so a denial is reproducible
and testable without a model.

Fails closed: an unknown action type is denied, not allowed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import (
    POLICY_VERSION,
    ActionType,
    Evidence,
    PolicyDecision,
    PolicyEffect,
)

# Autonomy tiers from docs/architecture/04-security-governance-and-safety.md 4.4
TIER_0_OBSERVE = 0
TIER_1_ANALYSE = 1
TIER_2_DRAFT = 2
TIER_3_COMMIT = 3
TIER_4_HIGH_CONSEQUENCE = 4


@dataclass(frozen=True)
class Rule:
    rule_id: str
    tier: int
    required_roles: tuple[str, ...]
    reason: str


# Tier 4 entries are prohibited for CAIRN outright. They are listed rather than omitted
# so that an attempt to invoke one produces an explicit, auditable denial instead of an
# "unknown action" error that could be mistaken for a bug.
RULES: dict[ActionType, Rule] = {
    ActionType.DRAFT_WORK_ORDER: Rule(
        "RULE-T2-DRAFT-WO", TIER_2_DRAFT, (), "Draft artefact, no external system is changed."
    ),
    ActionType.DRAFT_SHIFT_INSTRUCTION: Rule(
        "RULE-T2-DRAFT-SI", TIER_2_DRAFT, (), "Draft artefact, no external system is changed."
    ),
    ActionType.CREATE_WORK_ORDER: Rule(
        "RULE-T3-CREATE-WO",
        TIER_3_COMMIT,
        ("SHIFT_BOSS", "MAINTENANCE_PLANNER"),
        "Creates a committed maintenance record; requires an accountable approver.",
    ),
    ActionType.PUBLISH_SHIFT_INSTRUCTION: Rule(
        "RULE-T3-PUBLISH-SI",
        TIER_3_COMMIT,
        ("SHIFT_BOSS",),
        "Directs crews on shift; requires the accountable operations owner.",
    ),
    ActionType.CREATE_ESCALATION: Rule(
        "RULE-T3-ESCALATE", TIER_3_COMMIT, ("SHIFT_BOSS",), "Raises a tracked escalation record."
    ),
    ActionType.SEND_INTERNAL_NOTIFICATION: Rule(
        "RULE-T3-NOTIFY", TIER_3_COMMIT, ("SHIFT_BOSS",), "Sends an internal operational notification."
    ),
    ActionType.UPDATE_DECISION_STATUS: Rule(
        "RULE-T3-DECISION", TIER_3_COMMIT, ("SHIFT_BOSS",), "Updates the authoritative decision record."
    ),
    ActionType.OVERRIDE_SAFETY_INTERLOCK: Rule(
        "RULE-T4-PROHIBITED-INTERLOCK",
        TIER_4_HIGH_CONSEQUENCE,
        (),
        "Safety interlock changes are outside CAIRN's authority and require the certified control process.",
    ),
    ActionType.APPROVE_BLAST_PERMIT: Rule(
        "RULE-T4-PROHIBITED-PERMIT",
        TIER_4_HIGH_CONSEQUENCE,
        (),
        "Blast permit approval requires a certified shotfirer process outside CAIRN.",
    ),
    ActionType.CHANGE_ISOLATION_STATE: Rule(
        "RULE-T4-PROHIBITED-ISOLATION",
        TIER_4_HIGH_CONSEQUENCE,
        (),
        "Isolation state is a life-critical control; CAIRN has no control path to it.",
    ),
    ActionType.SET_CRUSHER_CONTROL_SETPOINT: Rule(
        "RULE-T4-PROHIBITED-OT",
        TIER_4_HIGH_CONSEQUENCE,
        (),
        "Direct process-control setpoints are Zone 0 operational technology; CAIRN has no control path.",
    ),
}

MAX_EVIDENCE_AGE_SECONDS = 1800


class PolicyService:
    """Stateless evaluator. Deterministic given the same inputs and policy version."""

    policy_version = POLICY_VERSION

    def evaluate(
        self,
        *,
        action_type: ActionType,
        actor_roles: tuple[str, ...] | list[str],
        correlation_id: str,
        decision_id: str,
        evidence: list[Evidence] | None = None,
    ) -> PolicyDecision:
        roles = tuple(actor_roles)
        rule = RULES.get(action_type)

        # Fail closed on anything the policy table does not explicitly permit.
        if rule is None:
            return PolicyDecision(
                policy_decision_id=decision_id,
                correlation_id=correlation_id,
                action_type=action_type,
                effect=PolicyEffect.DENY,
                tier=TIER_4_HIGH_CONSEQUENCE,
                reason="Action type is not present in the policy table. Failing closed.",
                rule_id="RULE-FAIL-CLOSED",
            )

        if rule.tier >= TIER_4_HIGH_CONSEQUENCE:
            return PolicyDecision(
                policy_decision_id=decision_id,
                correlation_id=correlation_id,
                action_type=action_type,
                effect=PolicyEffect.DENY,
                tier=rule.tier,
                reason=rule.reason,
                rule_id=rule.rule_id,
            )

        if rule.tier <= TIER_2_DRAFT:
            return PolicyDecision(
                policy_decision_id=decision_id,
                correlation_id=correlation_id,
                action_type=action_type,
                effect=PolicyEffect.ALLOW,
                tier=rule.tier,
                reason=rule.reason,
                rule_id=rule.rule_id,
            )

        # Tier 3: allowed only behind a scoped human approval from a permitted role.
        if evidence and all(e.stale for e in evidence):
            return PolicyDecision(
                policy_decision_id=decision_id,
                correlation_id=correlation_id,
                action_type=action_type,
                effect=PolicyEffect.DENY,
                tier=rule.tier,
                reason="Every supporting evidence item is stale. Refusing to commit on unverified state.",
                rule_id="RULE-T3-STALE-EVIDENCE",
                required_roles=list(rule.required_roles),
            )

        if not set(roles) & set(rule.required_roles):
            return PolicyDecision(
                policy_decision_id=decision_id,
                correlation_id=correlation_id,
                action_type=action_type,
                effect=PolicyEffect.DENY,
                tier=rule.tier,
                reason=(
                    f"Actor roles {sorted(roles)} do not include any role authorised for this action."
                ),
                rule_id=rule.rule_id,
                required_roles=list(rule.required_roles),
            )

        return PolicyDecision(
            policy_decision_id=decision_id,
            correlation_id=correlation_id,
            action_type=action_type,
            effect=PolicyEffect.ESCALATE,
            tier=rule.tier,
            reason=rule.reason,
            rule_id=rule.rule_id,
            required_roles=list(rule.required_roles),
        )


def is_prohibited(action_type: ActionType) -> bool:
    rule = RULES.get(action_type)
    return rule is None or rule.tier >= TIER_4_HIGH_CONSEQUENCE
