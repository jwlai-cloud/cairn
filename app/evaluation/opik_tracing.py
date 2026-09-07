"""Optional Opik tracing for the evaluation suite.

Opik (Comet, Apache-2) gives the evaluation runs a UI, dataset versioning and trend
lines across prompt and policy versions - the one thing the hand-rolled harness does
not provide.

It is deliberately optional. The suite is a release gate and must run on a clean
checkout with no account, no docker stack and no network, so nothing here may fail the
run. Enable with:

    uv pip install -e ".[eval]"
    CAIRN_OPIK=1 python -m app.evaluation

Without CAIRN_OPIK the module is inert and never imported.
"""

from __future__ import annotations

import os
from typing import Any

ENABLED_ENV = "CAIRN_OPIK"
PROJECT = os.getenv("CAIRN_OPIK_PROJECT", "cairn-evaluation")


def enabled() -> bool:
    return os.getenv(ENABLED_ENV, "").lower() in ("1", "true", "yes")


def log_report(report: Any) -> str | None:
    """Send one evaluation run to Opik. Returns a note for the operator, never raises."""
    if not enabled():
        return None
    try:
        import opik
    except ImportError:
        return "CAIRN_OPIK is set but opik is not installed. Run: uv pip install -e '.[eval]'"

    try:
        client = opik.Opik(project_name=PROJECT)
        trace = client.trace(
            name="cairn-evaluation",
            input={
                "policyVersion": report.policy_version,
                "promptVersion": report.prompt_version,
                "modelId": report.model_id,
            },
            output={"passed": report.passed, "failed": report.failed, "total": report.total},
            metadata={"credentialsRequired": report.credentials_required, **report.metrics},
            tags=["cairn", "evaluation", report.model_id],
        )
        for case in report.cases:
            trace.span(
                name=f"{case['case_id']} {case['title']}",
                type="general",
                input={"category": case["category"]},
                output={"passed": case["passed"], "detail": case["detail"], "failures": case["failures"]},
                metadata=case["metrics"],
            )
        trace.end()
        client.flush()
        return f"logged {report.total} cases to Opik project '{PROJECT}'"
    except Exception as exc:  # never fail the gate because telemetry is unavailable
        return f"Opik logging skipped: {type(exc).__name__}: {exc}"
