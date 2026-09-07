"""Bounded Strands Graph for the CAIRN vertical slice.

Topology is fixed at build time (ADR-002). The supervisor cannot invent nodes, edges or
tools at run time, because a high-consequence operational path has to be inspectable.

    situation ─┐
    reliability┤
    operations ┼─→ scenario_planner
    risk      ─┘

The four specialists reduce the injected event context. The planner reduces what those
four actually returned, delivered by the graph itself - so the edges carry data, not
just execution order.

Policy review, approval, action coordination and outcome verification are deterministic
services that sit *outside* this graph. The model proposes; it never authorises.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from strands import Agent
from strands.multiagent import GraphBuilder

from app.agents import reducers
from app.agents.context import GraphContext
from app.agents.fixture_model import FixtureModel
from app.agents.hooks import CairnAgentHooks, NodeTelemetry
from app.agents.tools import NODE_TOOLS, build_read_tools, tools_for
from app.domain.models import (
    MODEL_ID_FIXTURE,
    PROMPT_VERSION,
    ConstraintSet,
    NodeStatus,
    RiskAssessment,
    ScenarioSet,
    SituationSummary,
)

PROMPT_DIR = Path(__file__).parent / "prompts"

CORRELATION_ID = "corr_compound_disruption_v1"


def resolve_model_id_for(mode: str) -> str:
    """The model id this mode will actually use. Named before the run, not after."""
    if mode == "fixture":
        return MODEL_ID_FIXTURE
    from app.agents.bedrock_models import resolve_model_id
    from app.config import settings

    return resolve_model_id(settings.BEDROCK_REGION, settings.BEDROCK_MODEL_ID)

MAX_NODE_EXECUTIONS = 12
EXECUTION_TIMEOUT_SECONDS = 90
NODE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    label: str
    role: str
    prompt_file: str
    output_model: type[BaseModel]


SPECIALISTS: tuple[NodeSpec, ...] = (
    NodeSpec("situation", "Situation", "Correlates signals into one incident", "situation.v1.md", SituationSummary),
    NodeSpec("reliability", "Reliability", "Equipment and maintenance constraints", "reliability.v1.md", ConstraintSet),
    NodeSpec("operations", "Operations", "Feasible dispatch and production levers", "operations.v1.md", ConstraintSet),
    NodeSpec("risk", "Risk and HSE", "Hazards, controls and missing evidence", "risk.v1.md", RiskAssessment),
)
PLANNER = NodeSpec(
    "scenario_planner", "Scenario planner", "Ranks genuinely different options", "scenario_planner.v1.md", ScenarioSet
)

NODE_OUTPUT_MODELS: dict[str, type[BaseModel]] = {s.node_id: s.output_model for s in (*SPECIALISTS, PLANNER)}

# Read tools each node consults before answering, with their arguments. Deterministic on
# purpose: the same run always gathers the same evidence in the same order.
TOOL_PLANS: dict[str, tuple[tuple[str, dict], ...]] = {
    "situation": (("get_recent_events", {}), ("get_evidence", {})),
    "reliability": (
        ("get_maintenance_constraints", {}),
        ("get_asset_status", {"asset_id": "asset_primary_crusher_01"}),
        ("get_evidence", {}),
    ),
    "operations": (("get_production_constraints", {}),),
    # The risk prompt requires it to report missing evidence, so it has to read the
    # evidence set rather than reason about hazards from the weather alone.
    "risk": (("get_weather_window", {}), ("get_evidence", {})),
    "scenario_planner": (),
}


def load_prompt(spec: NodeSpec) -> str:
    return (PROMPT_DIR / spec.prompt_file).read_text()


def _reducer_for(spec: NodeSpec, ctx: GraphContext):
    """Bind a node's reducer. Specialists read the context; the planner reads its peers."""
    if spec.node_id == "situation":
        return lambda _upstream: reducers.situation(ctx)
    if spec.node_id == "reliability":
        return lambda _upstream: reducers.reliability(ctx)
    if spec.node_id == "operations":
        return lambda _upstream: reducers.operations(ctx)
    if spec.node_id == "risk":
        return lambda _upstream: reducers.risk(ctx)

    def plan(upstream: dict[str, dict[str, Any]]) -> ScenarioSet:
        # Revalidate the upstream payloads through the same contracts the specialists
        # emitted them under. If a dependency drifts off-contract, this raises here
        # rather than producing a confident plan built on a malformed input.
        return reducers.scenario_planner(
            ctx,
            situation_summary=SituationSummary.model_validate(upstream["situation"]),
            reliability_set=ConstraintSet.model_validate(upstream["reliability"]),
            operations_set=ConstraintSet.model_validate(upstream["operations"]),
            risk_assessment=RiskAssessment.model_validate(upstream["risk"]),
        )

    return plan


def _model_for(spec: NodeSpec, ctx: GraphContext, mode: str, model_id: str):
    if mode == "bedrock":  # pragma: no cover - requires AWS credentials, not exercised in CI
        from strands.models import BedrockModel

        from app.config import settings

        kwargs = {"region_name": settings.BEDROCK_REGION} if settings.BEDROCK_REGION else {}
        # model_id is resolved once per graph, never per node: resolving per node could
        # give different nodes different models, and would report one that did not run.
        return BedrockModel(model_id=model_id, temperature=0.0, **kwargs)
    requires = () if spec.node_id != PLANNER.node_id else tuple(s.node_id for s in SPECIALISTS)
    return FixtureModel(
        _reducer_for(spec, ctx),
        node_id=spec.node_id,
        structured_tool_name=spec.output_model.__name__,
        requires=requires,
        tool_plan=TOOL_PLANS.get(spec.node_id, ()),
    )


def _agent(
    spec: NodeSpec,
    ctx: GraphContext,
    mode: str,
    model_id: str,
    registry: dict,
    telemetry: dict[str, NodeTelemetry],
) -> Agent:
    allowed = NODE_TOOLS.get(spec.node_id, ())
    telemetry[spec.node_id] = NodeTelemetry(node_id=spec.node_id, allowed_tools=allowed)
    return Agent(
        model=_model_for(spec, ctx, mode, model_id),
        name=spec.node_id,
        description=spec.role,
        system_prompt=load_prompt(spec),
        structured_output_model=spec.output_model,
        tools=tools_for(spec.node_id, registry),
        hooks=[
            CairnAgentHooks(
                node_id=spec.node_id,
                allowed_tools=allowed,
                structured_tool_name=spec.output_model.__name__,
                correlation_id=CORRELATION_ID,
                telemetry=telemetry[spec.node_id],
            )
        ],
        callback_handler=None,
    )


@dataclass
class GraphRunResult:
    outputs: dict[str, BaseModel]
    timings: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, NodeStatus] = field(default_factory=dict)
    telemetry: dict[str, NodeTelemetry] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
    model_id: str = MODEL_ID_FIXTURE
    prompt_version: str = PROMPT_VERSION


def build_graph(ctx: GraphContext, mode: str = "fixture", model_id: str | None = None):
    """Construct the bounded graph. Same shape in fixture and bedrock mode.

    Returns the graph, the per-node telemetry the hook chain will fill in, and the
    model id every node was built with - resolved once here so the whole graph, the
    audit entry and any cost estimate all name the same model.
    """
    model_id = model_id or resolve_model_id_for(mode)
    registry = build_read_tools(ctx)
    telemetry: dict[str, NodeTelemetry] = {}
    builder = GraphBuilder()
    builder.set_graph_id("cairn-compound-disruption-v1")
    for spec in (*SPECIALISTS, PLANNER):
        builder.add_node(_agent(spec, ctx, mode, model_id, registry, telemetry), spec.node_id)
    for spec in SPECIALISTS:
        builder.set_entry_point(spec.node_id)            # four specialists run in parallel
        builder.add_edge(spec.node_id, PLANNER.node_id)  # planner waits for all four
    builder.set_max_node_executions(MAX_NODE_EXECUTIONS)
    builder.set_execution_timeout(EXECUTION_TIMEOUT_SECONDS)
    builder.set_node_timeout(NODE_TIMEOUT_SECONDS)
    return builder.build(), telemetry, model_id


async def run_graph(
    prompt: str, ctx: GraphContext, mode: str = "fixture", model_id: str | None = None
) -> GraphRunResult:
    graph, telemetry, resolved_model_id = build_graph(ctx, mode, model_id)
    started = time.perf_counter()
    result = await graph.invoke_async(prompt)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    outputs: dict[str, BaseModel] = {}
    statuses: dict[str, NodeStatus] = {}
    timings: dict[str, int] = {}
    usage: dict[str, int] = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
    for node_id, node_result in result.results.items():
        # Token accounting is only meaningful against a real provider; the fixture model
        # reports zeros. Read defensively - this is telemetry, never load-bearing.
        metrics = getattr(getattr(node_result, "result", None), "metrics", None)
        accumulated = getattr(metrics, "accumulated_usage", None) or {}
        for key in usage:
            usage[key] += int(accumulated.get(key, 0) or 0)

        structured = getattr(node_result.result, "structured_output", None)
        if structured is None:
            statuses[node_id] = NodeStatus.FAILED
            continue
        outputs[node_id] = structured
        statuses[node_id] = NodeStatus.COMPLETED
        # Prefer the hook-measured duration; it is observed, not estimated.
        measured = telemetry[node_id].duration_ms if node_id in telemetry else 0
        timings[node_id] = measured or int(getattr(node_result, "execution_time", 0)) or max(elapsed_ms // 5, 1)

    for node_id in {s.node_id for s in (*SPECIALISTS, PLANNER)} - set(outputs):
        statuses[node_id] = NodeStatus.FAILED

    return GraphRunResult(
        outputs=outputs,
        timings=timings,
        statuses=statuses,
        telemetry=telemetry,
        usage=usage,
        model_id=resolved_model_id,
    )
