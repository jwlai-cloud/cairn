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
from typing import Callable

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


class ExternalTimeout(Exception):
    """The external system did not answer after the request may already have applied."""


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


def _default_transport(request: ActionRequest) -> tuple[str, dict]:
    """Stand-in for the external system. Writes nowhere; returns the artefact it would create."""
    return _artefact(request)


@dataclass
class ActionGateway:
    """The only permitted path to a state change. Simulation-only in this build."""

    policy: PolicyService
    ledger: AuditLedger
    simulation_store: dict[str, dict] = field(default_factory=dict)
    # Seam for the external system, so a timeout can be exercised without one.
    transport: Callable[[ActionRequest], tuple[str, dict]] = _default_transport
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
            # Unknown outcome first: an action that may already have applied cannot be
            # retried at all, whatever payload the caller now presents.
            if prior.status is ActionStatus.UNKNOWN:
                raise ActionRejected(
                    "RECONCILIATION_REQUIRED",
                    "The previous attempt timed out with an unknown outcome. Reconcile it before retrying.",
                    {"actionId": prior.action_id, "idempotencyKey": prior.idempotency_key},
                )
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

        # Claim the key BEFORE calling out, so a timeout cannot be retried into a
        # second effect. The claim starts as IN_PROGRESS and is only resolved below.
        claim = ActionRecord(
            action_id=request.action_id,
            action_type=request.action_type,
            status=ActionStatus.IN_PROGRESS,
            idempotency_key=request.idempotency_key,
            request_hash=rhash,
            correlation_id=request.correlation_id,
            simulated=True,
            created_at=now,
            message="Claimed; awaiting the external system.",
        )
        self._by_idempotency_key[request.idempotency_key] = claim

        try:
            ref, artefact = self.transport(request)
        except ExternalTimeout as exc:
            # The call may or may not have applied. Fail into UNKNOWN and stop; never
            # retry blindly, because a blind retry is how one instruction becomes two.
            unknown = claim.model_copy(
                update={
                    "status": ActionStatus.UNKNOWN,
                    "message": f"Outcome unknown after timeout: {exc}. Reconciliation required.",
                }
            )
            self._by_idempotency_key[request.idempotency_key] = unknown
            self.records.append(unknown)
            self.ledger.record(
                "ACTION_UNKNOWN",
                request.actor_id,
                f"{request.action_type.value} timed out after it may have applied; entering UNKNOWN.",
                actionId=unknown.action_id,
                idempotencyKey=unknown.idempotency_key,
                requiresReconciliation=True,
            )
            return unknown

        record = claim.model_copy(
            update={
                "status": ActionStatus.SUCCEEDED,
                "artefact_ref": ref,
                "artefact": artefact,
                "message": "Simulated only. No external system was contacted.",
            }
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

    def reconcile(self, action_id: str, *, applied: bool, actor_id: str) -> ActionRecord:
        """Resolve an UNKNOWN outcome with evidence from the external system.

        Only a human or an authoritative read can close this out. The gateway will not
        guess, because guessing is what produces a duplicate work order.
        """
        record = next((r for r in self.records if r.action_id == action_id), None)
        if record is None:
            raise ActionRejected("NOT_FOUND", f"No action {action_id}.")
        if record.status is not ActionStatus.UNKNOWN:
            raise ActionRejected(
                "NOT_RECONCILABLE",
                f"Action {action_id} is {record.status.value}; only UNKNOWN can be reconciled.",
            )

        if applied:
            ref, artefact = _artefact_ref_for(record)
            resolved = record.model_copy(
                update={
                    "status": ActionStatus.SUCCEEDED,
                    "artefact_ref": ref,
                    "artefact": artefact,
                    "message": "Reconciled: the external system confirmed the effect applied.",
                }
            )
            self.simulation_store[ref] = artefact
        else:
            resolved = record.model_copy(
                update={
                    "status": ActionStatus.FAILED,
                    "message": "Reconciled: the external system confirmed no effect applied.",
                }
            )

        self._by_idempotency_key[record.idempotency_key] = resolved
        self.records[self.records.index(record)] = resolved
        self.ledger.record(
            "ACTION_RECONCILED",
            actor_id,
            f"{record.action_type.value} reconciled to {resolved.status.value}.",
            actionId=record.action_id,
            applied=applied,
        )
        return resolved


def _artefact_ref_for(record: ActionRecord) -> tuple[str, dict]:
    short = record.idempotency_key.split(":")[-1]
    return f"SIM-{record.action_type.value}-{short}", {
        "type": record.action_type.value,
        "system": "simulation-store (reconciled)",
    }
