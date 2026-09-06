"""Bounded Strands Graph for the CAIRN vertical slice.

Topology is fixed at build time (ADR-002). The supervisor cannot invent nodes, edges or
tools at run time, because a high-consequence operational path has to be inspectable.

    situation ─┐
    reliability┤
    operations ┼─→ scenario_planner
    risk      ─┘

Policy review, approval, action coordination and outcome verification are deterministic
services that sit *outside* this graph. The model proposes; it never authorises.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel
from strands import Agent
from strands.multiagent import GraphBuilder

from app.agents import fixture_outputs
from app.agents.fixture_model import FixtureModel
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

FIXTURE_PAYLOADS = {
    "situation": fixture_outputs.situation_summary,
    "reliability": fixture_outputs.reliability_constraints,
    "operations": fixture_outputs.operations_envelope,
    "risk": fixture_outputs.risk_assessment,
    "scenario_planner": fixture_outputs.scenario_set,
}


def load_prompt(spec: NodeSpec) -> str:
    return (PROMPT_DIR / spec.prompt_file).read_text()


def _model_for(spec: NodeSpec, mode: str):
    if mode == "bedrock":  # pragma: no cover - requires AWS credentials, not exercised in CI
        from strands.models import BedrockModel

        return BedrockModel(model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0", temperature=0.0)
    return FixtureModel(FIXTURE_PAYLOADS[spec.node_id](), node_id=spec.node_id)


def _agent(spec: NodeSpec, mode: str) -> Agent:
    return Agent(
        model=_model_for(spec, mode),
        name=spec.node_id,
        description=spec.role,
        system_prompt=load_prompt(spec),
        structured_output_model=spec.output_model,
        callback_handler=None,
    )


@dataclass
class GraphRunResult:
    outputs: dict[str, BaseModel]
    timings: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, NodeStatus] = field(default_factory=dict)
    model_id: str = MODEL_ID_FIXTURE
    prompt_version: str = PROMPT_VERSION


def build_graph(mode: str = "fixture"):
    """Construct the bounded graph. Same shape in fixture and bedrock mode."""
    builder = GraphBuilder()
    builder.set_graph_id("cairn-compound-disruption-v1")
    for spec in (*SPECIALISTS, PLANNER):
        builder.add_node(_agent(spec, mode), spec.node_id)
    for spec in SPECIALISTS:
        builder.set_entry_point(spec.node_id)          # four specialists run in parallel
        builder.add_edge(spec.node_id, PLANNER.node_id)  # planner waits for all four
    builder.set_max_node_executions(MAX_NODE_EXECUTIONS)
    builder.set_execution_timeout(EXECUTION_TIMEOUT_SECONDS)
    builder.set_node_timeout(NODE_TIMEOUT_SECONDS)
    return builder.build()


async def run_graph(prompt: str, mode: str = "fixture") -> GraphRunResult:
    graph = build_graph(mode)
    started = time.perf_counter()
    result = await graph.invoke_async(prompt)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    outputs: dict[str, BaseModel] = {}
    statuses: dict[str, NodeStatus] = {}
    timings: dict[str, int] = {}
    for node_id, node_result in result.results.items():
        structured = getattr(node_result.result, "structured_output", None)
        if structured is None:
            statuses[node_id] = NodeStatus.FAILED
            continue
        outputs[node_id] = structured
        statuses[node_id] = NodeStatus.COMPLETED
        timings[node_id] = int(getattr(node_result, "execution_time", 0)) or max(elapsed_ms // 5, 1)

    missing = {s.node_id for s in (*SPECIALISTS, PLANNER)} - set(outputs)
    for node_id in missing:
        statuses[node_id] = NodeStatus.FAILED

    return GraphRunResult(
        outputs=outputs,
        timings=timings,
        statuses=statuses,
        model_id=MODEL_ID_FIXTURE if mode == "fixture" else "bedrock",
    )
