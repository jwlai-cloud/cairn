"""Evaluation runner.

Runs the cases from docs/architecture/06 6.4 and reports the metrics from 6.5. It calls
no model and needs no credentials, so the same numbers come out on any machine.

    python -m app.evaluation                 # table to stdout
    python -m app.evaluation --json report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from app.agents.context import GraphContext
from app.agents.graph import run_graph
from app.domain.models import POLICY_VERSION, PROMPT_VERSION, MODEL_ID_FIXTURE
from app.evaluation.cases import ALL_CASES, CaseResult
from app.evaluation import opik_tracing
from app.integrations.fixture_source import FixtureSource


@dataclass
class EvaluationReport:
    passed: int
    failed: int
    total: int
    duration_ms: int
    policy_version: str = POLICY_VERSION
    prompt_version: str = PROMPT_VERSION
    model_id: str = MODEL_ID_FIXTURE
    credentials_required: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
    cases: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0


async def _decision_quality() -> dict[str, float]:
    """Constraint coverage and evidence coverage, measured on the full scenario."""
    source = FixtureSource()
    ctx = GraphContext(
        tuple(source.events()), tuple(source.evidence()), source.site_model(), source.baseline_kpi()
    )
    result = await run_graph("evaluation", ctx)
    planner = result.outputs["scenario_planner"]
    declared = {
        c.constraint_id
        for node in ("reliability", "operations")
        for c in result.outputs[node].constraints
    }
    referenced = {c for o in planner.options for c in o.constraints}
    material = [o for o in planner.options]

    tool_calls = [c for t in result.telemetry.values() for c in t.tool_calls]
    succeeded = [c for c in tool_calls if c.status == "success"]

    return {
        "constraintCoverage": round(len(referenced & declared) / max(len(referenced), 1), 3),
        "evidenceCoverage": round(sum(1 for o in material if o.evidence_ids) / max(len(material), 1), 3),
        "optionsWithAssumptions": round(
            sum(1 for o in material if o.assumptions and o.unknowns) / max(len(material), 1), 3
        ),
        "toolSuccessRate": round(len(succeeded) / max(len(tool_calls), 1), 3),
        "toolCalls": len(tool_calls),
        "modelCalls": sum(t.model_calls for t in result.telemetry.values()),
        "nodeLatencyMsMax": max((t.duration_ms for t in result.telemetry.values()), default=0),
    }


async def run_evaluation() -> EvaluationReport:
    started = time.perf_counter()
    results: list[CaseResult] = []
    for case in ALL_CASES:
        try:
            results.append(await case.run())
        except Exception as exc:  # a case that explodes is a failing case, not a crash
            results.append(
                CaseResult(
                    case_id=case.case_id, title=case.title, category=case.category,
                    passed=False, detail=f"raised {type(exc).__name__}: {exc}",
                    failures=["case raised"],
                )
            )

    metrics: dict[str, Any] = await _decision_quality()
    safety = [r for r in results if r.category == "safety"]
    metrics["safetyCasesPassed"] = sum(1 for r in safety if r.passed)
    metrics["safetyCaseCount"] = len(safety)
    metrics["prohibitedActionViolationRate"] = max(
        (r.metrics.get("violationRate", 0.0) for r in results), default=0.0
    )
    metrics["approvalBypassRate"] = max(
        (r.metrics.get("approvalBypassRate", 0.0) for r in results), default=0.0
    )
    metrics["replayMatchRate"] = next(
        (r.metrics.get("replayMatchRate", 0.0) for r in results if r.case_id == "EV-13"), 0.0
    )

    return EvaluationReport(
        passed=sum(1 for r in results if r.passed),
        failed=sum(1 for r in results if not r.passed),
        total=len(results),
        duration_ms=int((time.perf_counter() - started) * 1000),
        metrics=metrics,
        cases=[asdict(r) for r in results],
    )


def render(report: EvaluationReport) -> str:
    lines = [
        "CAIRN evaluation",
        f"  policy {report.policy_version} · prompts {report.prompt_version} · model {report.model_id}",
        f"  credentials required: {report.credentials_required}",
        "",
        f"  {'CASE':<7} {'RESULT':<7} {'CATEGORY':<12} TITLE",
    ]
    for case in report.cases:
        mark = "PASS" if case["passed"] else "FAIL"
        lines.append(f"  {case['case_id']:<7} {mark:<7} {case['category']:<12} {case['title']}")
        lines.append(f"  {'':<7} {'':<7} {'':<12} {case['detail']}")
        for failure in case["failures"]:
            lines.append(f"  {'':<7} {'':<7} {'':<12} FAILED CHECK: {failure}")
    lines += ["", "  metrics"]
    for key, value in sorted(report.metrics.items()):
        lines.append(f"    {key:<32} {value}")
    lines += ["", f"  {report.passed}/{report.total} passed in {report.duration_ms} ms"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CAIRN evaluation suite.")
    parser.add_argument("--json", metavar="PATH", help="also write the report as JSON")
    args = parser.parse_args()

    report = asyncio.run(run_evaluation())
    print(render(report))

    note = opik_tracing.log_report(report)
    if note:
        print(f"\n  {note}")
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(asdict(report), handle, indent=2, default=str)
        print(f"\n  report written to {args.json}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
