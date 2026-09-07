"""Tools are really called, and the hook chain really enforces the node allow-list.

The trap these guard against is the one the graph already fell into once: a component
that is present in the architecture, wired into the code, and does nothing.
"""

import pytest

from app.agents import graph as graph_module
from app.agents.context import GraphContext
from app.agents.graph import SPECIALISTS, run_graph
from app.agents.tools import NODE_TOOLS, build_read_tools
from app.domain.models import ActionType
from app.integrations.fixture_source import FixtureSource

PROMPT = "Compound disruption on Shift A at North Pit."


def context() -> GraphContext:
    s = FixtureSource()
    return GraphContext(tuple(s.events()), tuple(s.evidence()), s.site_model(), s.baseline_kpi())


# ------------------------------------------------------------------ tools really run


async def test_every_specialist_actually_calls_at_least_one_tool():
    result = await run_graph(PROMPT, context())
    for spec in SPECIALISTS:
        calls = result.telemetry[spec.node_id].tool_calls
        assert calls, f"{spec.node_id} completed without calling any tool"
        assert all(c.status == "success" for c in calls), calls
        assert all(c.response_hash for c in calls), "a tool result must be hashed for the audit"


async def test_tool_results_reach_the_agent_through_the_strands_loop():
    """More than one model call per specialist means the tool loop genuinely ran."""
    result = await run_graph(PROMPT, context())
    for spec in SPECIALISTS:
        telemetry = result.telemetry[spec.node_id]
        assert telemetry.model_calls == len(telemetry.tool_calls) + 1, (
            "each tool round trip should cost one model call, plus one for the typed output"
        )


async def test_hook_durations_are_measured_not_estimated():
    result = await run_graph(PROMPT, context())
    for spec in SPECIALISTS:
        assert result.telemetry[spec.node_id].duration_ms >= 0
        assert result.timings[spec.node_id] == result.telemetry[spec.node_id].duration_ms


# ------------------------------------------------------------- allow-list enforcement


async def test_a_tool_outside_the_node_allow_list_is_cancelled(monkeypatch):
    """The risk agent may not read production constraints, however it is prompted."""
    forbidden = "get_production_constraints"
    assert forbidden not in NODE_TOOLS["risk"]

    plans = dict(graph_module.TOOL_PLANS)
    plans["risk"] = ((forbidden, {}), *plans["risk"])
    monkeypatch.setattr(graph_module, "TOOL_PLANS", plans)

    result = await run_graph(PROMPT, context())
    blocked = result.telemetry["risk"].blocked_tools
    assert blocked, "the hook chain must cancel a tool that is not on the node's allow-list"
    assert blocked[0].tool_name == forbidden
    assert "allow-list" in blocked[0].reason
    assert result.statuses["risk"].value == "COMPLETED", "a blocked tool must not fail the node"


async def test_the_planner_has_no_tools_at_all():
    result = await run_graph(PROMPT, context())
    assert NODE_TOOLS["scenario_planner"] == ()
    assert result.telemetry["scenario_planner"].tool_calls == []


def test_no_agent_can_reach_a_state_changing_tool():
    """Read, proposal and state-changing tools are separate modules for exactly this."""
    registry = set(build_read_tools(context()))
    action_names = {a.value.lower() for a in ActionType}
    assert not registry & action_names
    for node, allowed in NODE_TOOLS.items():
        assert set(allowed) <= registry, f"{node} references a tool that does not exist"
        for name in allowed:
            assert not name.startswith(("create_", "publish_", "override_", "approve_", "set_", "change_")), name


@pytest.mark.parametrize("node_id", [s.node_id for s in SPECIALISTS])
def test_each_node_declares_a_non_empty_allow_list(node_id):
    assert NODE_TOOLS[node_id], f"{node_id} has no tools; it would be reasoning without evidence"


# ------------------------------------------------------------------------ audit trail


async def test_tool_calls_appear_in_the_audit_trail(analysed_run):
    stages = [e.stage for e in analysed_run.view().audit]
    assert "TOOL_CALL" in stages
    tool_entries = [e for e in analysed_run.view().audit if e.stage == "TOOL_CALL"]
    assert len(tool_entries) >= 6
    for entry in tool_entries:
        assert entry.refs["toolName"]
        assert entry.refs["status"] == "success"
        assert entry.refs["responseHash"]


async def test_the_read_model_exposes_what_each_agent_looked_at(analysed_run):
    agents = [n for n in analysed_run.view().nodes if n.kind == "strands-agent"]
    for node in agents:
        assert node.allowed_tools == list(NODE_TOOLS[node.node_id])
    situation = next(n for n in agents if n.node_id == "situation")
    assert [c.tool_name for c in situation.tool_calls] == ["get_recent_events", "get_evidence"]
