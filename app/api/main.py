"""CAIRN API and situation-room host.

The frontend consumes this read model and contains no policy logic. Every 4xx uses the
single error envelope from docs/architecture/05-interfaces-and-data-contracts.md 5.8.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.domain.models import (
    ActionType,
    ApiError,
    ApiErrorBody,
    ApprovalRequest,
    Incident,
    RunView,
    ScenarioOption,
)
from app.domain.run_service import CORRELATION_ID, RunStore
from app.tools.action_tools import ActionRejected

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

STATUS_BY_CODE = {
    "POLICY_DENIED": 403,
    "APPROVAL_REQUIRED": 403,
    "APPROVAL_INVALID": 403,
    "APPROVAL_OUT_OF_SCOPE": 403,
    "APPROVAL_REJECTED": 403,
    "APPROVAL_EXPIRED": 403,
    "VERSION_CONFLICT": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "NO_ACTION": 409,
    "RECONCILIATION_REQUIRED": 409,
    "NOT_RECONCILABLE": 409,
    "NOT_FOUND": 404,
}

app = FastAPI(title="CAIRN", version="0.1.0", description="Mine operations decision fabric (prototype)")
store = RunStore(mode=settings.MODE, audit_database=settings.AUDIT_DB)


@app.exception_handler(ActionRejected)
async def _rejected(_: Request, exc: ActionRejected) -> JSONResponse:
    body = ApiError(
        error=ApiErrorBody(
            code=exc.code, message=exc.message, details=exc.details, correlation_id=CORRELATION_ID
        )
    )
    return JSONResponse(status_code=STATUS_BY_CODE.get(exc.code, 400), content=body.model_dump(by_alias=True))


class ApprovalRequestBody(BaseModel):
    scenarioId: str


class ApprovalDecisionBody(BaseModel):
    approve: bool
    approverId: str = settings.ACTOR_ID
    approverRole: str = "SHIFT_SUPERVISOR"


class ProhibitedActionBody(BaseModel):
    actionType: ActionType = ActionType.OVERRIDE_SAFETY_INTERLOCK


class ReconcileBody(BaseModel):
    applied: bool


# ------------------------------------------------------------------ run lifecycle


@app.get("/v1/runs/current", response_model=RunView)
def get_current_run() -> RunView:
    return store.run.view()


@app.post("/v1/runs", response_model=RunView)
def create_run() -> RunView:
    return store.reset().view()


@app.post("/v1/runs/current/reset", response_model=RunView)
def reset_run() -> RunView:
    """Reset/replay control. A fresh run reproduces the same incident and options."""
    return store.reset().view()


@app.get("/v1/runs/current/signature")
def replay_signature() -> dict:
    return {"runId": store.run.view().run_id, "replaySignature": store.run.replay_signature()}


# ----------------------------------------------------------------------- events


@app.post("/v1/events/next", response_model=RunView)
def inject_next_event() -> RunView:
    store.run.inject_next_event()
    return store.run.view()


@app.post("/v1/events", response_model=RunView)
def inject_all_events() -> RunView:
    store.run.inject_all_events()
    return store.run.view()


# ------------------------------------------------------------------------ agents


@app.post("/v1/runs/current/analyse", response_model=RunView)
async def analyse() -> RunView:
    if not store.run.injected_event_ids:
        store.run.inject_all_events()
    await store.run.analyse()
    return store.run.view()


@app.get("/v1/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str) -> Incident:
    incident = store.run.incident()
    if incident is None or incident.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


# --------------------------------------------------------------------- scenarios


@app.get("/v1/scenarios/{scenario_id}", response_model=ScenarioOption)
def get_scenario(scenario_id: str) -> ScenarioOption:
    try:
        return store.run.scenario(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scenario not found") from None


@app.post("/v1/scenarios/{scenario_id}/select", response_model=RunView)
def select_scenario(scenario_id: str) -> RunView:
    try:
        store.run.select_scenario(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scenario not found") from None
    return store.run.view()


# --------------------------------------------------------------------- approvals


@app.post("/v1/approvals", response_model=RunView)
def request_approval(body: ApprovalRequestBody) -> RunView:
    store.run.request_approval(body.scenarioId, actor_roles=list(settings.ACTOR_ROLES))
    return store.run.view()


@app.post("/v1/approvals/decision", response_model=RunView)
def decide_approval(body: ApprovalDecisionBody) -> RunView:
    store.run.decide_approval(
        approve=body.approve, approver_id=body.approverId, approver_role=body.approverRole
    )
    return store.run.view()


@app.get("/v1/approvals/current", response_model=ApprovalRequest)
def current_approval() -> ApprovalRequest:
    if store.run.approval is None:
        raise HTTPException(status_code=404, detail="No approval pending")
    return store.run.approval


# ----------------------------------------------------------------------- actions


@app.post("/v1/actions", response_model=RunView)
def execute_actions() -> RunView:
    store.run.execute_approved_actions(
        actor_id=settings.ACTOR_ID, actor_roles=list(settings.ACTOR_ROLES)
    )
    return store.run.view()


@app.post("/v1/actions/prohibited", response_model=RunView)
def attempt_prohibited(body: ProhibitedActionBody) -> RunView:
    """Deliberate negative case. Always denied by the policy table, never by a model."""
    store.run.attempt_prohibited_action(
        action_type=body.actionType, actor_id=settings.ACTOR_ID, actor_roles=list(settings.ACTOR_ROLES)
    )
    return store.run.view()


@app.post("/v1/actions/timeout", response_model=RunView)
def simulate_timeout() -> RunView:
    """Demo control: the external system times out after the call may have applied."""
    store.run.simulate_action_timeout(actor_id=settings.ACTOR_ID, actor_roles=list(settings.ACTOR_ROLES))
    return store.run.view()


@app.post("/v1/actions/{action_id}/reconcile", response_model=RunView)
def reconcile_action(action_id: str, body: ReconcileBody) -> RunView:
    """Resolve an UNKNOWN outcome with evidence. The gateway will not guess."""
    store.run.reconcile_action(action_id, applied=body.applied, actor_id=settings.ACTOR_ID)
    return store.run.view()


@app.post("/v1/outcome/verify", response_model=RunView)
def verify_outcome() -> RunView:
    store.run.verify_outcome()
    return store.run.view()


# ------------------------------------------------------------------------- audit


@app.get("/v1/audit/{correlation_id}")
def get_audit(correlation_id: str) -> dict:
    if correlation_id != CORRELATION_ID:
        raise HTTPException(status_code=404, detail="Unknown correlation id")
    view = store.run.view()
    return {
        "correlationId": correlation_id,
        "policyVersion": view.policy_version,
        "promptVersion": view.prompt_version,
        "modelId": view.model_id,
        "entries": [e.model_dump(by_alias=True) for e in view.audit],
    }


@app.get("/v1/audit/{correlation_id}/history")
def get_audit_history(correlation_id: str) -> dict:
    """Every entry recorded for this correlation id, across runs and process restarts.

    With CAIRN_AUDIT_DB set this outlives the process; without it, it is this session.
    """
    if correlation_id != CORRELATION_ID:
        raise HTTPException(status_code=404, detail="Unknown correlation id")
    entries = store.audit_history()
    return {
        "correlationId": correlation_id,
        "durable": settings.AUDIT_DB is not None,
        "entryCount": len(entries),
        "entries": [e.model_dump(by_alias=True) for e in entries],
    }


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok",
        "mode": settings.MODE,
        "credentialsRequired": settings.MODE != "fixture",
        "durableAudit": settings.AUDIT_DB is not None,
    }


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
