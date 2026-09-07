"""CAIRN API and situation-room host.

The frontend consumes this read model and contains no policy logic. Every 4xx uses the
single error envelope from docs/architecture/05-interfaces-and-data-contracts.md 5.8.

Each visitor gets their own run, keyed by a cookie. A single process-wide run is fine on
a laptop and wrong the moment this is hosted: two people opening the same link would
share one run, so one pressing Reset would wipe the other's demo while they watched it.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
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
from app.domain.run_service import CORRELATION_ID, Run, SessionRunStore
from app.tools.action_tools import ActionRejected

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
SESSION_COOKIE = "cairn_session"
SESSION_MAX_AGE = 60 * 60 * 8
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

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
store = SessionRunStore(mode=settings.MODE, audit_database=settings.AUDIT_DB)


def session_id(request: Request, response: Response) -> str:
    """Read the visitor's session, minting one if absent or malformed."""
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid or not _SESSION_RE.match(sid):
        sid = secrets.token_urlsafe(18)
    # Refreshed on every call so a long demo cannot expire mid-walkthrough.
    response.set_cookie(
        SESSION_COOKIE, sid, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax", path="/"
    )
    return sid


def current_run(sid: str = Depends(session_id)) -> Run:
    return store.run_for(sid)


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
def get_current_run(run: Run = Depends(current_run)) -> RunView:
    return run.view()


@app.post("/v1/runs", response_model=RunView)
def create_run(sid: str = Depends(session_id)) -> RunView:
    return store.reset(sid).view()


@app.post("/v1/runs/current/reset", response_model=RunView)
def reset_run(sid: str = Depends(session_id)) -> RunView:
    """Reset/replay control. A fresh run reproduces the same incident and options."""
    return store.reset(sid).view()


@app.get("/v1/runs/current/signature")
def replay_signature(run: Run = Depends(current_run)) -> dict:
    return {"runId": run.view().run_id, "replaySignature": run.replay_signature()}


# ----------------------------------------------------------------------- events


@app.post("/v1/events/next", response_model=RunView)
def inject_next_event(run: Run = Depends(current_run)) -> RunView:
    run.inject_next_event()
    return run.view()


@app.post("/v1/events", response_model=RunView)
def inject_all_events(run: Run = Depends(current_run)) -> RunView:
    run.inject_all_events()
    return run.view()


# ------------------------------------------------------------------------ agents


@app.post("/v1/runs/current/analyse", response_model=RunView)
async def analyse(run: Run = Depends(current_run)) -> RunView:
    if not run.injected_event_ids:
        run.inject_all_events()
    await run.analyse()
    return run.view()


@app.get("/v1/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str, run: Run = Depends(current_run)) -> Incident:
    incident = run.incident()
    if incident is None or incident.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


# --------------------------------------------------------------------- scenarios


@app.get("/v1/scenarios/{scenario_id}", response_model=ScenarioOption)
def get_scenario(scenario_id: str, run: Run = Depends(current_run)) -> ScenarioOption:
    try:
        return run.scenario(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scenario not found") from None


@app.post("/v1/scenarios/{scenario_id}/select", response_model=RunView)
def select_scenario(scenario_id: str, run: Run = Depends(current_run)) -> RunView:
    try:
        run.select_scenario(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scenario not found") from None
    return run.view()


# --------------------------------------------------------------------- approvals


@app.post("/v1/approvals", response_model=RunView)
def request_approval(body: ApprovalRequestBody, run: Run = Depends(current_run)) -> RunView:
    run.request_approval(body.scenarioId, actor_roles=list(settings.ACTOR_ROLES))
    return run.view()


@app.post("/v1/approvals/decision", response_model=RunView)
def decide_approval(body: ApprovalDecisionBody, run: Run = Depends(current_run)) -> RunView:
    run.decide_approval(approve=body.approve, approver_id=body.approverId, approver_role=body.approverRole)
    return run.view()


@app.get("/v1/approvals/current", response_model=ApprovalRequest)
def current_approval(run: Run = Depends(current_run)) -> ApprovalRequest:
    if run.approval is None:
        raise HTTPException(status_code=404, detail="No approval pending")
    return run.approval


# ----------------------------------------------------------------------- actions


@app.post("/v1/actions", response_model=RunView)
def execute_actions(run: Run = Depends(current_run)) -> RunView:
    run.execute_approved_actions(actor_id=settings.ACTOR_ID, actor_roles=list(settings.ACTOR_ROLES))
    return run.view()


@app.post("/v1/actions/prohibited", response_model=RunView)
def attempt_prohibited(body: ProhibitedActionBody, run: Run = Depends(current_run)) -> RunView:
    """Deliberate negative case. Always denied by the policy table, never by a model."""
    run.attempt_prohibited_action(
        action_type=body.actionType, actor_id=settings.ACTOR_ID, actor_roles=list(settings.ACTOR_ROLES)
    )
    return run.view()


@app.post("/v1/actions/timeout", response_model=RunView)
def simulate_timeout(run: Run = Depends(current_run)) -> RunView:
    """Demo control: the external system times out after the call may have applied."""
    run.simulate_action_timeout(actor_id=settings.ACTOR_ID, actor_roles=list(settings.ACTOR_ROLES))
    return run.view()


@app.post("/v1/actions/{action_id}/reconcile", response_model=RunView)
def reconcile_action(action_id: str, body: ReconcileBody, run: Run = Depends(current_run)) -> RunView:
    """Resolve an UNKNOWN outcome with evidence. The gateway will not guess."""
    run.reconcile_action(action_id, applied=body.applied, actor_id=settings.ACTOR_ID)
    return run.view()


@app.post("/v1/outcome/verify", response_model=RunView)
def verify_outcome(run: Run = Depends(current_run)) -> RunView:
    run.verify_outcome()
    return run.view()


# ------------------------------------------------------------------------- audit


@app.get("/v1/audit/{correlation_id}")
def get_audit(correlation_id: str, run: Run = Depends(current_run)) -> dict:
    if correlation_id != CORRELATION_ID:
        raise HTTPException(status_code=404, detail="Unknown correlation id")
    view = run.view()
    return {
        "correlationId": correlation_id,
        "policyVersion": view.policy_version,
        "promptVersion": view.prompt_version,
        "modelId": view.model_id,
        "entries": [e.model_dump(by_alias=True) for e in view.audit],
    }


@app.get("/v1/audit/{correlation_id}/history")
def get_audit_history(correlation_id: str, sid: str = Depends(session_id)) -> dict:
    """Every entry this session has recorded, across its own runs and process restarts."""
    if correlation_id != CORRELATION_ID:
        raise HTTPException(status_code=404, detail="Unknown correlation id")
    entries = store.audit_history(sid)
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
        "activeSessions": store.session_count,
    }


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
