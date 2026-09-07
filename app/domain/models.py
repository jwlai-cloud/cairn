"""CAIRN domain contracts.

Contract-first (docs/architecture/05-interfaces-and-data-contracts.md): these models
are the public boundary. Wire format is camelCase; Python stays snake_case.

Every agent-boundary object carries provenance (evidenceIds, assumptions, unknowns,
confidence) because a fluent explanation is not operational evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

SCHEMA_VERSION = "1.0"
POLICY_VERSION = "policy-2026.09.1"
PROMPT_VERSION = "prompts-v1"
MODEL_ID_FIXTURE = "cairn-fixture-deterministic-v1"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Contract(BaseModel):
    """Base for every wire-visible contract object."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


# --------------------------------------------------------------------------- enums


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    CRITICAL_OPERATIONAL = "CRITICAL_OPERATIONAL"


class AssetState(str, Enum):
    """Drives scene colour. green / amber / red / blue in the UI."""

    NORMAL = "NORMAL"
    CONSTRAINED = "CONSTRAINED"
    FAILED = "FAILED"
    SELECTED = "SELECTED"


class EventType(str, Enum):
    ASSET_DEGRADED = "ASSET_DEGRADED"
    ASSET_UNAVAILABLE = "ASSET_UNAVAILABLE"
    WEATHER_ALERT = "WEATHER_ALERT"
    MAINTENANCE_CONSTRAINT = "MAINTENANCE_CONSTRAINT"
    PERMIT_CONFLICT = "PERMIT_CONFLICT"
    PRODUCTION_CONSTRAINT = "PRODUCTION_CONSTRAINT"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    ACTION_FAILED = "ACTION_FAILED"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    # Tier 2 - draft only
    DRAFT_WORK_ORDER = "DRAFT_WORK_ORDER"
    DRAFT_SHIFT_INSTRUCTION = "DRAFT_SHIFT_INSTRUCTION"
    # Tier 3 - commit, requires approval token
    CREATE_WORK_ORDER = "CREATE_WORK_ORDER"
    PUBLISH_SHIFT_INSTRUCTION = "PUBLISH_SHIFT_INSTRUCTION"
    CREATE_ESCALATION = "CREATE_ESCALATION"
    SEND_INTERNAL_NOTIFICATION = "SEND_INTERNAL_NOTIFICATION"
    UPDATE_DECISION_STATUS = "UPDATE_DECISION_STATUS"
    # Tier 4 - prohibited for the MVP, no approval can unlock these
    OVERRIDE_SAFETY_INTERLOCK = "OVERRIDE_SAFETY_INTERLOCK"
    APPROVE_BLAST_PERMIT = "APPROVE_BLAST_PERMIT"
    CHANGE_ISOLATION_STATE = "CHANGE_ISOLATION_STATE"
    SET_CRUSHER_CONTROL_SETPOINT = "SET_CRUSHER_CONTROL_SETPOINT"


class PolicyEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    CONSUMED = "CONSUMED"


class ActionStatus(str, Enum):
    PLANNED = "PLANNED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"


class RunStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NodeStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Confidence(Contract):
    value: float = Field(ge=0.0, le=1.0)
    basis: str


# ------------------------------------------------------------------- site read model


class Point(Contract):
    x: float
    y: float
    z: float = 0.0


class Asset(Contract):
    asset_id: str
    name: str
    kind: str  # CRUSHER | PLANT | STOCKPILE | WORKSHOP | TRUCK | BENCH | WEATHER_ZONE
    position: Point
    state: AssetState = AssetState.NORMAL
    capacity_percent: float = 100.0
    detail: str = ""
    home_route_id: str | None = None


class Route(Contract):
    route_id: str
    name: str
    path: list[Point]
    open: bool = True
    exposed_to_weather: bool = False
    detail: str = ""


class SiteModel(Contract):
    schema_version: str = SCHEMA_VERSION
    site_id: str
    name: str
    shift_label: str
    assets: list[Asset]
    routes: list[Route]


class Kpi(Contract):
    tonnes_moved: int
    tonnes_target: int
    crusher_availability_percent: float
    active_trucks: int
    weather_window_minutes: int | None
    unresolved_risks: int


# ----------------------------------------------------------------------- evidence


class Evidence(Contract):
    evidence_id: str
    source_system: str
    source_record_id: str
    observed_at: datetime
    received_at: datetime
    freshness_seconds: int
    reliability: float = Field(ge=0.0, le=1.0)
    data_classification: DataClassification = DataClassification.INTERNAL
    summary: str
    stale: bool = False
    conflicts_with: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------------- events


class EventSource(Contract):
    system: str
    source_record_id: str
    observed_at: datetime
    received_at: datetime


class OperationalEvent(Contract):
    schema_version: str = SCHEMA_VERSION
    event_id: str
    event_type: EventType
    source: EventSource
    site_id: str
    asset_id: str | None = None
    route_id: str | None = None
    location_id: str | None = None
    severity: Severity
    status: str = "OPEN"
    title: str
    measurements: dict[str, float] = Field(default_factory=dict)
    freshness_seconds: int = 0
    evidence_ids: list[str] = Field(default_factory=list)
    offset_seconds: int = 0  # deterministic replay offset from shift start
    metadata: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------- agent structured IO


class AgentOutputBase(Contract):
    schema_version: str = SCHEMA_VERSION
    producer: str
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class SituationSummary(AgentOutputBase):
    headline: str
    narrative: str
    affected_asset_ids: list[str]
    affected_route_ids: list[str] = Field(default_factory=list)
    correlated_event_ids: list[str]


class Constraint(Contract):
    constraint_id: str
    description: str
    hard: bool  # a hard constraint cannot be traded away by any scenario


class ConstraintSet(AgentOutputBase):
    headline: str
    constraints: list[Constraint]


class RiskFinding(AgentOutputBase):
    risk_id: str
    hazard: str
    control: str
    severity: Severity
    time_bound_minutes: int | None = None
    affected_route_ids: list[str] = Field(default_factory=list)
    # A binding control is not discretionary: no scenario may trade it away, and the
    # planner derives its route closures from exactly these findings.
    binding: bool = False


class RiskAssessment(AgentOutputBase):
    headline: str
    findings: list[RiskFinding]


class ScenarioImpacts(Contract):
    estimated_throughput_delta: float  # fraction, negative is a loss
    estimated_tonnes_delta: int
    estimated_recovery_minutes: int
    affected_assets: list[str]
    affected_routes: list[str] = Field(default_factory=list)


class ScenarioOption(Contract):
    schema_version: str = SCHEMA_VERSION
    scenario_id: str
    scenario_version: int = 1
    key: str  # protect_safety | recover_tonnes | preserve_equipment
    title: str
    summary: str
    status: str = "PROPOSED"
    objective_weights: dict[str, float]
    assumptions: list[str]
    unknowns: list[str]
    constraints: list[str]
    impacts: ScenarioImpacts
    safety_risk_level: Severity
    risk_findings: list[str] = Field(default_factory=list)
    required_approvals: list[str]
    requested_action_types: list[ActionType]
    evidence_ids: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    route_overlay: list[str] = Field(default_factory=list)  # routes highlighted when selected
    closed_route_ids: list[str] = Field(default_factory=list)


class ScenarioSet(AgentOutputBase):
    headline: str
    options: list[ScenarioOption]
    recommended_scenario_id: str
    recommendation_reason: str
    would_change_if: str


# ------------------------------------------------------------------ policy/approval


class PolicyDecision(Contract):
    schema_version: str = SCHEMA_VERSION
    policy_decision_id: str
    policy_version: str = POLICY_VERSION
    correlation_id: str
    action_type: ActionType
    effect: PolicyEffect
    tier: int
    reason: str
    required_roles: list[str] = Field(default_factory=list)
    rule_id: str
    evaluated_at: datetime = Field(default_factory=utcnow)
    evaluated_by: str = "deterministic-policy-service"


class ApprovalScope(Contract):
    site_id: str
    asset_ids: list[str]


class ApprovalRequest(Contract):
    schema_version: str = SCHEMA_VERSION
    approval_id: str
    correlation_id: str
    scenario_id: str
    scenario_version: int
    requested_action_types: list[ActionType]
    scope: ApprovalScope
    required_roles: list[str]
    policy_decision_ids: list[str]
    created_at: datetime
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver_id: str | None = None
    approver_role: str | None = None
    decided_at: datetime | None = None
    conditions: list[str] = Field(default_factory=list)
    approval_token: str | None = None
    evidence_hash: str


class ActionRequest(Contract):
    schema_version: str = SCHEMA_VERSION
    action_id: str
    action_type: ActionType
    approval_token: str | None
    idempotency_key: str
    actor_id: str
    tenant_id: str = "demo-mining-co"
    site_id: str
    policy_decision_id: str | None
    correlation_id: str
    expected_version: int
    reason: str
    payload: dict[str, Any]


class ActionRecord(Contract):
    schema_version: str = SCHEMA_VERSION
    action_id: str
    action_type: ActionType
    status: ActionStatus
    idempotency_key: str
    request_hash: str
    correlation_id: str
    simulated: bool = True
    artefact_ref: str | None = None
    artefact: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    replayed: bool = False
    message: str = ""


class OutcomeReport(AgentOutputBase):
    headline: str
    verified: bool
    tonnes_recovered: int
    crusher_availability_percent: float
    residual_risks: list[str]
    unresolved_items: list[str]
    action_ids: list[str]


# -------------------------------------------------------------------------- errors


class ApiErrorBody(Contract):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str


class ApiError(Contract):
    error: ApiErrorBody


# --------------------------------------------------------------- run / read model


class ToolCallRecord(Contract):
    """One tool invocation observed by the Strands hook chain."""

    tool_name: str
    status: str  # success | error | blocked
    duration_ms: int = 0
    response_hash: str = ""
    blocked: bool = False
    reason: str = ""


class AgentNodeRun(Contract):
    node_id: str
    label: str
    role: str
    kind: str  # "strands-agent" | "deterministic-service"
    status: NodeStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    headline: str = ""
    findings: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    confidence: float | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    # Deliberately no chain-of-thought field. Status, findings, evidence, uncertainty only.


class Incident(Contract):
    schema_version: str = SCHEMA_VERSION
    incident_id: str
    correlation_id: str
    title: str
    narrative: str
    severity: Severity
    status: str
    event_ids: list[str]
    affected_asset_ids: list[str]
    affected_route_ids: list[str]
    weather_window_minutes: int | None = None
    confidence: float
    opened_at: datetime


class AuditEntry(Contract):
    seq: int
    at: datetime
    stage: str
    actor: str
    summary: str
    refs: dict[str, Any] = Field(default_factory=dict)


class RunView(Contract):
    """The single read model the frontend renders. No policy logic lives client-side."""

    schema_version: str = SCHEMA_VERSION
    run_id: str
    correlation_id: str
    tenant_id: str = "demo-mining-co"
    site_id: str
    status: RunStatus
    mode: str
    model_id: str
    policy_version: str = POLICY_VERSION
    prompt_version: str = PROMPT_VERSION
    site: SiteModel
    kpi: Kpi
    baseline_kpi: Kpi
    events: list[OperationalEvent]
    evidence: list[Evidence]
    incident: Incident | None = None
    nodes: list[AgentNodeRun]
    scenarios: list[ScenarioOption] = Field(default_factory=list)
    recommended_scenario_id: str | None = None
    recommendation_reason: str = ""
    would_change_if: str = ""
    selected_scenario_id: str | None = None
    approval: ApprovalRequest | None = None
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    actions: list[ActionRecord] = Field(default_factory=list)
    outcome: OutcomeReport | None = None
    audit: list[AuditEntry] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    stale_evidence_ids: list[str] = Field(default_factory=list)
    conflict_notes: list[str] = Field(default_factory=list)
