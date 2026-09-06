"""Simulation-only state-changing tools plus the action gateway.

Nothing here reaches a real system. Every artefact is written to an in-process
simulation store. The gateway is the only path from CAIRN to a "state change" and it
enforces, in this order: policy allow, valid unexpired approval token, matching scope
and plan version, then idempotent claim.

Read/proposal/state-changing tools are separate modules on purpose: a read-only
specialist cannot reach a write tool by wording its prompt differently.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.audit.ledger import AuditLedger
from app.domain.models import (
    ActionRecord,
    ActionRequest,
    ActionStatus,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
    Evidence,
    PolicyEffect,
    utcnow,
)
from app.policy.decisions import PolicyService


class ActionRejected(Exception):
    """Raised when the gateway refuses an action. Carries the API error code."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def request_hash(request: ActionRequest) -> str:
    body = json.dumps(
        {
            "actionType": request.action_type.value,
            "siteId": request.site_id,
            "expectedVersion": request.expected_version,
            "payload": request.payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()[:32]


def _artefact(request: ActionRequest) -> tuple[str, dict]:
    """Build the simulated artefact. Prefixed SIM- so it can never be mistaken for real."""
    short = request.idempotency_key.split(":")[-1]
    if request.action_type is ActionType.CREATE_WORK_ORDER:
        return f"SIM-WO-{short}", {
            "type": "WORK_ORDER",
            "system": "simulation-store (no CMMS connected)",
            "priority": request.payload.get("priority", "HIGH"),
            "assetId": request.payload.get("assetId"),
            "description": request.payload.get("description", ""),
        }
    if request.action_type is ActionType.PUBLISH_SHIFT_INSTRUCTION:
        return f"SIM-SI-{short}", {
            "type": "SHIFT_INSTRUCTION",
            "system": "simulation-store (no dispatch connected)",
            "audience": request.payload.get("audience", "Shift A haul crews"),
            "instruction": request.payload.get("instruction", ""),
        }
    return f"SIM-{request.action_type.value}-{short}", {
        "type": request.action_type.value,
        "system": "simulation-store",
        **request.payload,
    }


@dataclass
class ActionGateway:
    """The only permitted path to a state change. Simulation-only in this build."""

    policy: PolicyService
    ledger: AuditLedger
    simulation_store: dict[str, dict] = field(default_factory=dict)
    _by_idempotency_key: dict[str, ActionRecord] = field(default_factory=dict)
    records: list[ActionRecord] = field(default_factory=list)
    policy_decisions: list = field(default_factory=list)

    def execute(
        self,
        request: ActionRequest,
        *,
        approval: ApprovalRequest | None,
        actor_roles: list[str],
        evidence: list[Evidence] | None = None,
        now=None,
    ) -> ActionRecord:
        now = now or utcnow()
        rhash = request_hash(request)

        # 1. Policy first. A denial here is model-independent and terminal.
        decision = self.policy.evaluate(
            action_type=request.action_type,
            actor_roles=actor_roles,
            correlation_id=request.correlation_id,
            decision_id=f"pol_{rhash[:12]}",
            evidence=evidence,
        )
        self.policy_decisions.append(decision)
        self.ledger.record(
            "POLICY_DECISION",
            "deterministic-policy-service",
            f"{decision.effect.value} {request.action_type.value}: {decision.reason}",
            policyDecisionId=decision.policy_decision_id,
            ruleId=decision.rule_id,
            tier=decision.tier,
            policyVersion=decision.policy_version,
        )
        if decision.effect is PolicyEffect.DENY:
            raise ActionRejected(
                "POLICY_DENIED",
                decision.reason,
                {
                    "ruleId": decision.rule_id,
                    "tier": decision.tier,
                    "requiredRoles": decision.required_roles,
                    "policyVersion": decision.policy_version,
                    "actionType": request.action_type.value,
                },
            )

        # 2. Approval must exist, be approved, unexpired, in scope, and match the plan.
        if approval is None:
            raise ActionRejected("APPROVAL_REQUIRED", "No approval record exists for this action.")
        if approval.status is ApprovalStatus.EXPIRED or approval.expires_at <= now:
            raise ActionRejected(
                "APPROVAL_EXPIRED",
                "The approval expired before the action was submitted. Failing closed.",
                {"approvalId": approval.approval_id, "expiresAt": approval.expires_at.isoformat()},
            )
        if approval.status is ApprovalStatus.REJECTED:
            raise ActionRejected("APPROVAL_REJECTED", "The approver rejected this plan.")
        if approval.status not in (ApprovalStatus.APPROVED, ApprovalStatus.CONSUMED):
            raise ActionRejected(
                "APPROVAL_REQUIRED",
                f"Approval is {approval.status.value}; a state change needs an APPROVED approval.",
            )
        if not request.approval_token or request.approval_token != approval.approval_token:
            raise ActionRejected("APPROVAL_INVALID", "Approval token missing or does not match.")
        if request.action_type not in approval.requested_action_types:
            raise ActionRejected(
                "APPROVAL_OUT_OF_SCOPE",
                f"{request.action_type.value} is outside the approved action scope.",
                {"approvedActionTypes": [a.value for a in approval.requested_action_types]},
            )
        if request.expected_version != approval.scenario_version:
            raise ActionRejected(
                "VERSION_CONFLICT",
                "The plan changed after approval. The approval is superseded.",
                {"approvedVersion": approval.scenario_version, "requestedVersion": request.expected_version},
            )

        # 3. Idempotency: claim the key before producing any effect.
        prior = self._by_idempotency_key.get(request.idempotency_key)
        if prior is not None:
            if prior.request_hash != rhash:
                raise ActionRejected(
                    "IDEMPOTENCY_CONFLICT",
                    "The same idempotency key was reused with a different payload.",
                    {"idempotencyKey": request.idempotency_key},
                )
            replay = prior.model_copy(update={"replayed": True, "message": "Replayed prior result; no new side effect."})
            self.ledger.record(
                "ACTION_REPLAYED",
                request.actor_id,
                f"Duplicate {request.action_type.value} replayed from idempotency key.",
                actionId=prior.action_id,
                idempotencyKey=request.idempotency_key,
            )
            return replay

        ref, artefact = _artefact(request)
        record = ActionRecord(
            action_id=request.action_id,
            action_type=request.action_type,
            status=ActionStatus.SUCCEEDED,
            idempotency_key=request.idempotency_key,
            request_hash=rhash,
            correlation_id=request.correlation_id,
            simulated=True,
            artefact_ref=ref,
            artefact=artefact,
            created_at=now,
            message="Simulated only. No external system was contacted.",
        )
        self._by_idempotency_key[request.idempotency_key] = record
        self.simulation_store[ref] = artefact
        self.records.append(record)
        self.ledger.record(
            "ACTION_EXECUTED",
            request.actor_id,
            f"{request.action_type.value} simulated as {ref}.",
            actionId=record.action_id,
            idempotencyKey=record.idempotency_key,
            approvalId=approval.approval_id,
            policyDecisionId=decision.policy_decision_id,
            simulated=True,
        )
        return record
