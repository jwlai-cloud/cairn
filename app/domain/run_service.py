"""Run service: the deterministic shell around the bounded graph.

Everything that decides *what is permitted* lives here or in app/policy, never in the
graph. The graph produces findings and options; this service applies policy, holds the
approval, drives the simulation-only action gateway, verifies the outcome, and writes
the audit chain.

Deterministic by construction: fixed IDs, fixed fixture, fixed ordering. The only
non-deterministic values are wall-clock timestamps, which are excluded from
`replay_signature`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta

from app.agents.context import GraphContext
from app.agents.graph import PLANNER, SPECIALISTS, resolve_model_id_for, run_graph
from app.audit.ledger import AuditLedger
from app.audit.store import AuditStore, build_store
from app.domain.models import (
    MODEL_ID_FIXTURE,
    POLICY_VERSION,
    PROMPT_VERSION,
    ActionRequest,
    ActionType,
    AgentNodeRun,
    ApprovalRequest,
    ApprovalScope,
    ApprovalStatus,
    Asset,
    AssetState,
    ConstraintSet,
    Evidence,
    Incident,
    Kpi,
    NodeStatus,
    OperationalEvent,
    PolicyEffect,
    RiskAssessment,
    RunStatus,
    RunView,
    ScenarioOption,
    ScenarioSet,
    Severity,
    SituationSummary,
    utcnow,
)
from app.integrations.fixture_source import FixtureSource
from app.policy.decisions import PolicyService
from app.tools.action_tools import ActionGateway, ActionRejected, ExternalTimeout
from app.tools.proposal_tools import (
    calculate_production_impact,
    check_spatial_temporal_conflicts,
    draft_shift_instruction,
    draft_work_order,
)
from app.tools.read_tools import ReadTools

RUN_ID = "run_compound_disruption_v1"
CORRELATION_ID = "corr_compound_disruption_v1"
INCIDENT_ID = "inc_compound_disruption_v1"
APPROVAL_TTL = timedelta(minutes=15)

DETERMINISTIC_SERVICE_NODES = (
    ("policy_reviewer", "Policy review", "Deterministic allow/deny/escalate", "deterministic-service"),
    ("action_coordinator", "Action coordinator", "Idempotent simulated actions", "deterministic-service"),
    ("outcome_verifier", "Outcome verifier", "Confirms effect against new evidence", "deterministic-service"),
)


def _token(approval_id: str, scenario_id: str, version: int) -> str:
    """Deterministic opaque approval token. Server-issued; the client never mints one."""
    raw = f"{approval_id}|{scenario_id}|{version}|{POLICY_VERSION}".encode()
    return "apt_" + hashlib.sha256(raw).hexdigest()[:40]


@dataclass
class Run:
    """One replayable demo run. In-memory by design: no database in the vertical slice."""

    mode: str = "fixture"
    source: FixtureSource = field(default_factory=FixtureSource)
    audit_store: AuditStore | None = None
    ledger: AuditLedger = field(init=False)
    policy: PolicyService = field(default_factory=PolicyService)
    injected_event_ids: list[str] = field(default_factory=list)
    nodes: dict[str, AgentNodeRun] = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    scenarios: list[ScenarioOption] = field(default_factory=list)
    selected_scenario_id: str | None = None
    approval: ApprovalRequest | None = None
    outcome=None
    status: RunStatus = RunStatus.IDLE
    notices: list[str] = field(default_factory=list)
    conflict_notes: list[str] = field(default_factory=list)
    recommended_scenario_id: str | None = None
    recommendation_reason: str = ""
    would_change_if: str = ""
    # Set from the graph result, so the audit names the model that actually ran.
    model_id: str = MODEL_ID_FIXTURE
    gateway: ActionGateway = field(init=False)
    reads: ReadTools = field(init=False)

    def __post_init__(self) -> None:
        self.ledger = AuditLedger(CORRELATION_ID, store=self.audit_store)
        self.gateway = ActionGateway(policy=self.policy, ledger=self.ledger)
        self.reads = ReadTools(self.source)
        self._init_nodes()

    # ------------------------------------------------------------------ lifecycle

    def _init_nodes(self) -> None:
        self.nodes = {}
        for spec in (*SPECIALISTS, PLANNER):
            self.nodes[spec.node_id] = AgentNodeRun(
                node_id=spec.node_id,
                label=spec.label,
                role=spec.role,
                kind="strands-agent",
                status=NodeStatus.PENDING,
            )
        for node_id, label, role, kind in DETERMINISTIC_SERVICE_NODES:
            self.nodes[node_id] = AgentNodeRun(
                node_id=node_id, label=label, role=role, kind=kind, status=NodeStatus.PENDING
            )

    # -------------------------------------------------------------------- events

    @property
    def events(self) -> list[OperationalEvent]:
        wanted = set(self.injected_event_ids)
        return [e for e in self.source.events() if e.event_id in wanted]

    @property
    def evidence(self) -> list[Evidence]:
        ids = {eid for e in self.events for eid in e.evidence_ids}
        if self.outputs:
            ids |= {eid for o in self.outputs.values() for eid in getattr(o, "evidence_ids", [])}
        return [e for e in self.source.evidence() if e.evidence_id in ids]

    def inject_next_event(self) -> OperationalEvent | None:
        remaining = [e for e in self.source.events() if e.event_id not in self.injected_event_ids]
        if not remaining:
            return None
        event = remaining[0]
        self.injected_event_ids.append(event.event_id)
        self.ledger.record(
            "EVENT_INGESTED",
            event.source.system,
            f"{event.event_type.value}: {event.title}",
            eventId=event.event_id,
            sourceRecordId=event.source.source_record_id,
            evidenceIds=event.evidence_ids,
            freshnessSeconds=event.freshness_seconds,
        )
        return event

    def inject_all_events(self) -> list[OperationalEvent]:
        while self.inject_next_event() is not None:
            pass
        return self.events

    # ---------------------------------------------------------------- graph run

    async def analyse(self) -> None:
        """Run the bounded graph, then correlate its typed outputs into one incident."""
        if not self.injected_event_ids:
            raise ValueError("No events have been injected; nothing to analyse.")
        self.status = RunStatus.RUNNING
        # Resolve up front so the GRAPH_STARTED entry names the model that is about to
        # run, rather than the default it would otherwise still be holding.
        self.model_id = resolve_model_id_for(self.mode)
        self.ledger.record(
            "GRAPH_STARTED",
            "cairn-supervisor",
            f"Bounded graph invoked over {len(self.events)} correlated events.",
            promptVersion=PROMPT_VERSION,
            modelId=self.model_id,
            nodes=[s.node_id for s in (*SPECIALISTS, PLANNER)],
        )

        titles = "; ".join(e.title for e in self.events)
        context = GraphContext(
            events=tuple(self.events),
            evidence=tuple(self.evidence),
            site=self.source.site_model(),
            baseline_kpi=self.source.baseline_kpi(),
        )
        result = await run_graph(
            f"Compound disruption on Shift A at North Pit. Signals: {titles}",
            context,
            self.mode,
            # Reuse the id already named in GRAPH_STARTED so the audit entry and the
            # run cannot describe different models.
            model_id=self.model_id,
        )
        self.outputs = result.outputs
        self.model_id = result.model_id

        started = utcnow()
        for spec in (*SPECIALISTS, PLANNER):
            out = result.outputs.get(spec.node_id)
            node = self.nodes[spec.node_id]
            node.status = result.statuses.get(spec.node_id, NodeStatus.FAILED)
            node.started_at = started
            node.completed_at = utcnow()
            node.duration_ms = result.timings.get(spec.node_id)
            if out is None:
                continue
            node.headline = getattr(out, "headline", "")
            node.evidence_ids = list(getattr(out, "evidence_ids", []))
            node.assumptions = list(getattr(out, "assumptions", []))
            node.unknowns = list(getattr(out, "unknowns", []))
            node.confidence = getattr(out, "confidence", None)
            node.findings = self._findings_for(out)

            # Tool activity comes from the Strands hook chain, so the audit shows what the
            # agent actually looked at rather than what it claimed to look at.
            telemetry = result.telemetry.get(spec.node_id)
            if telemetry is not None:
                node.tool_calls = list(telemetry.tool_calls)
                node.allowed_tools = list(telemetry.allowed_tools)
                for call in telemetry.tool_calls:
                    self.ledger.record(
                        "TOOL_BLOCKED" if call.blocked else "TOOL_CALL",
                        spec.node_id,
                        call.reason or f"{call.tool_name} returned {call.status}",
                        toolName=call.tool_name,
                        status=call.status,
                        durationMs=call.duration_ms,
                        responseHash=call.response_hash or None,
                    )
            self.ledger.record(
                "AGENT_FINDING",
                spec.node_id,
                node.headline,
                evidenceIds=node.evidence_ids,
                confidence=node.confidence,
                unknowns=node.unknowns,
                promptVersion=PROMPT_VERSION,
                toolCalls=[c.tool_name for c in node.tool_calls],
            )

        planner: ScenarioSet = result.outputs[PLANNER.node_id]
        self.scenarios = list(planner.options)
        self.recommended_scenario_id = planner.recommended_scenario_id
        self.recommendation_reason = planner.recommendation_reason
        self.would_change_if = planner.would_change_if

        self._flag_stale_and_conflicting()
        self._flag_temporal_conflicts()
        self.status = RunStatus.AWAITING_APPROVAL
        self.ledger.record(
            "SCENARIOS_PROPOSED",
            PLANNER.node_id,
            f"{len(self.scenarios)} options proposed; recommendation {self.recommended_scenario_id}.",
            scenarioIds=[s.scenario_id for s in self.scenarios],
            recommendedScenarioId=self.recommended_scenario_id,
        )

    @staticmethod
    def _findings_for(out) -> list[str]:
        if isinstance(out, SituationSummary):
            return [out.narrative]
        if isinstance(out, ConstraintSet):
            return [f"{'HARD' if c.hard else 'soft'}: {c.description}" for c in out.constraints]
        if isinstance(out, RiskAssessment):
            return [f"{f.severity.value}: {f.hazard} -> control: {f.control}" for f in out.findings]
        if isinstance(out, ScenarioSet):
            return [f"{o.title}: {o.summary}" for o in out.options]
        return []

    def _flag_stale_and_conflicting(self) -> None:
        """Surface stale and conflicting sources rather than silently choosing one."""
        for e in self.evidence:
            if e.stale:
                self.notices.append(
                    f"STALE EVIDENCE {e.evidence_id}: {e.summary} Confirm before relying on it."
                )
                self.ledger.record("EVIDENCE_STALE", "evidence-validator", e.summary, evidenceId=e.evidence_id)
        seen: set[frozenset[str]] = set()
        for e in self.evidence:
            for other_id in e.conflicts_with:
                pair = frozenset({e.evidence_id, other_id})
                if pair in seen:
                    continue
                seen.add(pair)
                self.conflict_notes.append(
                    f"CONFLICT {e.evidence_id} vs {other_id}: both retained; planning uses the earlier arrival."
                )
                self.ledger.record(
                    "EVIDENCE_CONFLICT",
                    "evidence-validator",
                    f"{e.evidence_id} conflicts with {other_id}; neither discarded.",
                    evidenceIds=sorted(pair),
                )

    def _flag_temporal_conflicts(self) -> None:
        window = self.weather_window_minutes
        for option in self.scenarios:
            for note in check_spatial_temporal_conflicts(option, window):
                if note not in option.unknowns:
                    option.unknowns.append(note)

    # ------------------------------------------------------------------ incident

    @property
    def weather_window_minutes(self) -> int | None:
        weather = next((e for e in self.events if e.event_type.value == "WEATHER_ALERT"), None)
        if weather is None:
            return None
        return int(weather.measurements.get("minutesToClosure", 0))

    def incident(self) -> Incident | None:
        summary: SituationSummary | None = self.outputs.get("situation")
        if summary is None:
            return None
        return Incident(
            incident_id=INCIDENT_ID,
            correlation_id=CORRELATION_ID,
            title=summary.headline,
            narrative=summary.narrative,
            severity=Severity.HIGH,
            status="RECOVERY IN PROGRESS" if self.gateway.records else "OPEN",
            event_ids=summary.correlated_event_ids,
            affected_asset_ids=summary.affected_asset_ids,
            affected_route_ids=summary.affected_route_ids,
            weather_window_minutes=self.weather_window_minutes,
            confidence=summary.confidence,
            opened_at=self.source.events()[0].source.received_at,
        )

    # ------------------------------------------------------------------ scenarios

    def scenario(self, scenario_id: str) -> ScenarioOption:
        found = next((s for s in self.scenarios if s.scenario_id == scenario_id), None)
        if found is None:
            raise KeyError(scenario_id)
        return found

    def select_scenario(self, scenario_id: str) -> ScenarioOption:
        option = self.scenario(scenario_id)
        self.selected_scenario_id = scenario_id
        # Selecting a different plan invalidates any approval scoped to the previous one.
        if self.approval and self.approval.scenario_id != scenario_id:
            self.approval = self.approval.model_copy(update={"status": ApprovalStatus.SUPERSEDED})
            self.ledger.record(
                "APPROVAL_SUPERSEDED",
                "approval-service",
                "Selected plan changed; the previous approval no longer applies.",
                approvalId=self.approval.approval_id,
            )
        self.ledger.record(
            "SCENARIO_SELECTED", "user_shift_boss_01", f"{option.title} selected for review.", scenarioId=scenario_id
        )
        return option

    # ------------------------------------------------------------------- approval

    def request_approval(self, scenario_id: str, *, actor_roles: list[str]) -> ApprovalRequest:
        """Policy decides whether an approval is even offerable. Escalate means 'a human must sign'."""
        option = self.select_scenario(scenario_id)
        node = self.nodes["policy_reviewer"]
        node.status = NodeStatus.RUNNING

        decisions = [
            self.policy.evaluate(
                action_type=action_type,
                actor_roles=actor_roles,
                correlation_id=CORRELATION_ID,
                decision_id=f"pol_{option.scenario_id}_{action_type.value.lower()}",
                evidence=self.evidence,
            )
            for action_type in option.requested_action_types
        ]
        self.gateway.policy_decisions.extend(decisions)
        for d in decisions:
            self.ledger.record(
                "POLICY_DECISION",
                "deterministic-policy-service",
                f"{d.effect.value} {d.action_type.value}: {d.reason}",
                policyDecisionId=d.policy_decision_id,
                ruleId=d.rule_id,
                tier=d.tier,
                policyVersion=d.policy_version,
            )

        denied = [d for d in decisions if d.effect is PolicyEffect.DENY]
        node.status = NodeStatus.COMPLETED
        node.headline = (
            f"{len(decisions)} action types evaluated against {POLICY_VERSION}"
            if not denied
            else f"DENIED: {denied[0].reason}"
        )
        node.findings = [f"{d.effect.value} {d.action_type.value} ({d.rule_id})" for d in decisions]
        if denied:
            raise ActionRejected("POLICY_DENIED", denied[0].reason, {"ruleId": denied[0].rule_id})

        now = utcnow()
        approval_id = f"apr_{option.scenario_id}_{option.scenario_version}"
        self.approval = ApprovalRequest(
            approval_id=approval_id,
            correlation_id=CORRELATION_ID,
            scenario_id=option.scenario_id,
            scenario_version=option.scenario_version,
            requested_action_types=list(option.requested_action_types),
            scope=ApprovalScope(site_id=self.source.site_model().site_id, asset_ids=option.impacts.affected_assets),
            required_roles=list(option.required_approvals),
            policy_decision_ids=[d.policy_decision_id for d in decisions],
            created_at=now,
            expires_at=now + APPROVAL_TTL,
            status=ApprovalStatus.PENDING,
            conditions=["Simulation only. No external mine system is contacted."],
            evidence_hash=self._evidence_hash(option),
        )
        self.ledger.record(
            "APPROVAL_REQUESTED",
            "approval-service",
            f"Approval required from {', '.join(option.required_approvals)} before any state change.",
            approvalId=approval_id,
            scenarioId=option.scenario_id,
            expiresAt=self.approval.expires_at.isoformat(),
        )
        return self.approval

    def _evidence_hash(self, option: ScenarioOption) -> str:
        """Binds the approval to the exact evidence set. If evidence moves, the approval is void."""
        payload = json.dumps(sorted(option.evidence_ids), separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def decide_approval(
        self, *, approve: bool, approver_id: str, approver_role: str, now=None
    ) -> ApprovalRequest:
        if self.approval is None:
            raise ActionRejected("APPROVAL_REQUIRED", "No approval is pending.")
        now = now or utcnow()
        if self.approval.expires_at <= now:
            self.approval = self.approval.model_copy(update={"status": ApprovalStatus.EXPIRED})
            self.ledger.record("APPROVAL_EXPIRED", "approval-service", "Approval expired before a decision.")
            raise ActionRejected("APPROVAL_EXPIRED", "The approval expired before a decision was recorded.")
        if approver_role not in self.approval.required_roles:
            self.ledger.record(
                "APPROVAL_REJECTED",
                approver_id,
                f"Role {approver_role} is not among {self.approval.required_roles}.",
            )
            raise ActionRejected(
                "APPROVAL_INVALID",
                f"Role {approver_role} may not approve this plan.",
                {"requiredRoles": self.approval.required_roles},
            )

        if approve:
            token = _token(self.approval.approval_id, self.approval.scenario_id, self.approval.scenario_version)
            self.approval = self.approval.model_copy(
                update={
                    "status": ApprovalStatus.APPROVED,
                    "approver_id": approver_id,
                    "approver_role": approver_role,
                    "decided_at": now,
                    "approval_token": token,
                }
            )
            self.ledger.record(
                "APPROVAL_GRANTED",
                approver_id,
                f"{approver_role} approved {self.approval.scenario_id} (simulation only).",
                approvalId=self.approval.approval_id,
                scenarioVersion=self.approval.scenario_version,
                evidenceHash=self.approval.evidence_hash,
            )
        else:
            self.approval = self.approval.model_copy(
                update={
                    "status": ApprovalStatus.REJECTED,
                    "approver_id": approver_id,
                    "approver_role": approver_role,
                    "decided_at": now,
                }
            )
            self.ledger.record("APPROVAL_REJECTED", approver_id, f"{approver_role} rejected the plan.")
        return self.approval

    # -------------------------------------------------------------------- actions

    def execute_approved_actions(self, *, actor_id: str, actor_roles: list[str], transport=None) -> list:
        if self.approval is None or self.selected_scenario_id is None:
            raise ActionRejected("APPROVAL_REQUIRED", "Nothing has been approved.")
        option = self.scenario(self.selected_scenario_id)
        node = self.nodes["action_coordinator"]
        node.status = NodeStatus.RUNNING

        records = []
        for action_type in option.requested_action_types:
            payload = (
                draft_work_order(option, "asset_primary_crusher_01")
                if action_type is ActionType.CREATE_WORK_ORDER
                else draft_shift_instruction(option)
            )
            request = ActionRequest(
                action_id=f"act_{option.scenario_id}_{action_type.value.lower()}",
                action_type=action_type,
                approval_token=self.approval.approval_token,
                idempotency_key=f"act:v1:{option.scenario_id}:{action_type.value.lower()}",
                actor_id=actor_id,
                site_id=self.source.site_model().site_id,
                policy_decision_id=self.approval.policy_decision_ids[0] if self.approval.policy_decision_ids else None,
                correlation_id=CORRELATION_ID,
                expected_version=option.scenario_version,
                reason=option.title,
                payload=payload,
            )
            records.append(
                self.gateway.execute(
                    request,
                    approval=self.approval,
                    actor_roles=actor_roles,
                    evidence=self.evidence,
                    transport=transport,
                )
            )

        from app.domain.models import ActionStatus

        if not any(r.status is ActionStatus.UNKNOWN for r in records):
            self.approval = self.approval.model_copy(update={"status": ApprovalStatus.CONSUMED})
        node.status = NodeStatus.COMPLETED
        node.headline = f"{len(records)} simulated artefact(s) created"
        node.findings = [f"{r.action_type.value} -> {r.artefact_ref}" for r in records]
        return records

    def attempt_prohibited_action(self, *, action_type: ActionType, actor_id: str, actor_roles: list[str]):
        """The demo's policy-denial moment. No model is consulted; the denial is a table lookup."""
        request = ActionRequest(
            action_id=f"act_prohibited_{action_type.value.lower()}",
            action_type=action_type,
            approval_token=self.approval.approval_token if self.approval else None,
            idempotency_key=f"act:v1:prohibited:{action_type.value.lower()}",
            actor_id=actor_id,
            site_id=self.source.site_model().site_id,
            policy_decision_id=None,
            correlation_id=CORRELATION_ID,
            expected_version=1,
            reason="Operator attempted a high-consequence override from the situation room.",
            payload={"assetId": "asset_primary_crusher_01", "requestedBy": actor_id},
        )
        return self.gateway.execute(request, approval=self.approval, actor_roles=actor_roles, evidence=self.evidence)

    def simulate_action_timeout(self, *, actor_id: str, actor_roles: list[str]):
        """Run the approved actions against an external system that times out.

        Exercises the case from docs/architecture/06 6.4 #9: the call may already have
        applied, so the action must land in UNKNOWN rather than be retried blindly.

        The override is passed per call rather than swapped onto the shared gateway, so
        a concurrent action on the same run cannot be dragged through it.
        """

        def timing_out(_request):
            raise ExternalTimeout("no response from the simulated work-order system after 30s")

        return self.execute_approved_actions(
            actor_id=actor_id, actor_roles=actor_roles, transport=timing_out
        )

    def reconcile_action(self, action_id: str, *, applied: bool, actor_id: str):
        return self.gateway.reconcile(action_id, applied=applied, actor_id=actor_id)

    # -------------------------------------------------------------------- outcome

    def verify_outcome(self):
        from app.domain.models import OutcomeReport

        if not self.gateway.records or self.selected_scenario_id is None:
            raise ActionRejected("NO_ACTION", "No simulated action has been executed yet.")
        option = self.scenario(self.selected_scenario_id)
        node = self.nodes["outcome_verifier"]
        node.status = NodeStatus.RUNNING

        projected = calculate_production_impact(self.source.baseline_kpi(), option)
        residual = [
            f"{f.risk_id}: {f.hazard}"
            for f in self.outputs["risk"].findings
            if f.risk_id not in option.risk_findings
        ]
        self.outcome = OutcomeReport(
            producer="outcome_verifier",
            headline=(
                f"{option.title} executed in simulation. Projected {projected.tonnes_moved} t "
                f"against a {projected.tonnes_target} t target."
            ),
            verified=True,
            tonnes_recovered=option.impacts.estimated_tonnes_delta,
            crusher_availability_percent=projected.crusher_availability_percent,
            residual_risks=residual,
            unresolved_items=[
                "Truck 204 repair is queued for next shift and is not covered by this plan",
                "Weather source disagreement remains unresolved; the earlier arrival was used",
            ],
            action_ids=[r.action_id for r in self.gateway.records],
            evidence_ids=option.evidence_ids,
            assumptions=option.assumptions,
            unknowns=option.unknowns,
            confidence=0.8,
        )
        node.status = NodeStatus.COMPLETED
        node.headline = self.outcome.headline
        node.findings = self.outcome.unresolved_items
        node.confidence = self.outcome.confidence
        self.status = RunStatus.COMPLETED
        self.ledger.record(
            "OUTCOME_VERIFIED",
            "outcome-verifier",
            self.outcome.headline,
            actionIds=self.outcome.action_ids,
            residualRisks=len(residual),
            simulated=True,
        )
        return self.outcome

    # ------------------------------------------------------------------ read model

    def kpi(self) -> Kpi:
        baseline = self.source.baseline_kpi()
        availability = baseline.crusher_availability_percent
        active = baseline.active_trucks
        for e in self.events:
            if e.event_type.value == "ASSET_DEGRADED":
                availability = e.measurements.get("capacityPercent", availability)
            if e.event_type.value == "ASSET_UNAVAILABLE":
                active -= 1
        live = Kpi(
            tonnes_moved=baseline.tonnes_moved,
            tonnes_target=baseline.tonnes_target,
            crusher_availability_percent=availability,
            active_trucks=active,
            weather_window_minutes=self.weather_window_minutes,
            unresolved_risks=len(self.outputs["risk"].findings) if "risk" in self.outputs else 0,
        )
        if self.outcome is None or not self.selected_scenario_id:
            return live

        # A verified plan projects tonnes and crusher feed forward, but it does not undo
        # the disruption: Truck 204 is still down and the residual risks are still open.
        projected = calculate_production_impact(baseline, self.scenario(self.selected_scenario_id))
        return live.model_copy(
            update={
                "tonnes_moved": projected.tonnes_moved,
                "crusher_availability_percent": projected.crusher_availability_percent,
                "unresolved_risks": len(self.outcome.residual_risks),
            }
        )

    def site_with_states(self) -> "object":
        """Apply event-derived states so the scene colours come from the read model, not the client."""
        site = self.source.site_model()
        degraded = {e.asset_id for e in self.events if e.event_type.value == "ASSET_DEGRADED"}
        unavailable = {e.asset_id for e in self.events if e.event_type.value == "ASSET_UNAVAILABLE"}
        constrained = {e.asset_id for e in self.events if e.event_type.value in ("MAINTENANCE_CONSTRAINT", "PRODUCTION_CONSTRAINT")}
        weather_assets = {e.asset_id for e in self.events if e.event_type.value == "WEATHER_ALERT"}
        closed_routes: set[str] = set()
        if self.selected_scenario_id:
            closed_routes = set(self.scenario(self.selected_scenario_id).closed_route_ids)

        assets: list[Asset] = []
        for a in site.assets:
            state = a.state
            capacity = a.capacity_percent
            if a.asset_id in unavailable:
                state = AssetState.FAILED
                capacity = 0.0
            elif a.asset_id in degraded:
                state = AssetState.FAILED
                capacity = next(
                    (e.measurements.get("capacityPercent", 75.0) for e in self.events if e.asset_id == a.asset_id),
                    75.0,
                )
            elif a.asset_id in constrained or a.asset_id in weather_assets:
                state = AssetState.CONSTRAINED
            assets.append(a.model_copy(update={"state": state, "capacity_percent": capacity}))

        routes = [r.model_copy(update={"open": r.route_id not in closed_routes}) for r in site.routes]
        return site.model_copy(update={"assets": assets, "routes": routes})

    def view(self) -> RunView:
        return RunView(
            run_id=RUN_ID,
            correlation_id=CORRELATION_ID,
            site_id=self.source.site_model().site_id,
            status=self.status,
            mode=self.mode,
            model_id=self.model_id,
            site=self.site_with_states(),
            kpi=self.kpi(),
            baseline_kpi=self.source.baseline_kpi(),
            events=self.events,
            evidence=self.evidence,
            incident=self.incident(),
            nodes=list(self.nodes.values()),
            scenarios=self.scenarios,
            recommended_scenario_id=self.recommended_scenario_id,
            recommendation_reason=self.recommendation_reason,
            would_change_if=self.would_change_if,
            selected_scenario_id=self.selected_scenario_id,
            approval=self.approval,
            policy_decisions=list(self.gateway.policy_decisions),
            actions=list(self.gateway.records),
            outcome=self.outcome,
            audit=self.ledger.entries,
            notices=list(self.notices),
            stale_evidence_ids=[e.evidence_id for e in self.evidence if e.stale],
            conflict_notes=list(self.conflict_notes),
        )

    def replay_signature(self) -> str:
        """Hash of everything a replay must reproduce. Wall-clock fields are excluded."""
        view = self.view()
        payload = {
            "events": [e.event_id for e in view.events],
            "incident": view.incident.title if view.incident else None,
            "affected": sorted(view.incident.affected_asset_ids) if view.incident else [],
            "nodes": {n.node_id: [n.status.value, n.headline, n.confidence] for n in view.nodes},
            "scenarios": [
                [s.scenario_id, s.impacts.estimated_tonnes_delta, s.impacts.estimated_recovery_minutes,
                 s.safety_risk_level.value, sorted(s.evidence_ids), s.confidence, sorted(s.unknowns)]
                for s in view.scenarios
            ],
            "recommended": view.recommended_scenario_id,
            "policy": [[d.action_type.value, d.effect.value, d.rule_id] for d in view.policy_decisions],
            "actions": [[a.action_type.value, a.artefact_ref, a.status.value] for a in view.actions],
            "outcome": view.outcome.headline if view.outcome else None,
            "audit": [[e.stage, e.actor] for e in view.audit],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class RunStore:
    """Single active run. Reset replaces it, which is what makes replay reliable.

    The audit store is shared across resets on purpose: replaying the demo must not
    erase the record of what was decided before, only start a new run against it.
    """

    def __init__(self, mode: str = "fixture", audit_database: str | None = None) -> None:
        self.mode = mode
        self.audit_store = build_store(audit_database)
        self._run = Run(mode=mode, audit_store=self.audit_store)

    @property
    def run(self) -> Run:
        return self._run

    def reset(self) -> Run:
        self._run = Run(mode=self.mode, audit_store=self.audit_store)
        return self._run

    def audit_history(self) -> list:
        """Every entry ever recorded for this correlation id, across runs and restarts."""
        return self.audit_store.entries_for_correlation(CORRELATION_ID)
