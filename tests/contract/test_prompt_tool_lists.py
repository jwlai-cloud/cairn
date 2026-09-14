"""A prompt must not advertise a tool the node cannot call.

The prompts are the instructions a real model reads. Fixture mode never reads them - the
fixture provider follows TOOL_PLANS - so three prompts drifted unnoticed: the risk agent
was offered `get_active_permits` and the planner `simulate_recovery_plan`, neither of
which exists anywhere, and the planner was offered two functions that run deterministically
after the graph and are not tools at all. A real model told it has a tool will try to use
it, and the allow-list hook then cancels the call.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agents.graph import PLANNER, SPECIALISTS
from app.agents.tools import NODE_TOOLS, build_read_tools

PROMPTS = Path(__file__).resolve().parents[2] / "app" / "agents" / "prompts"
NODES = [s.node_id for s in (*SPECIALISTS, PLANNER)]


def advertised(node_id: str) -> set[str]:
    """Tool names in the prompt's 'Allowed tools' section."""
    text = (PROMPTS / f"{node_id}.v1.md").read_text()
    section = re.search(r"## Allowed tools\n(.*?)(?:\n## |\Z)", text, re.S)
    assert section, f"{node_id} prompt has no Allowed tools section"
    return set(re.findall(r"`([a-z_]+)`", section.group(1)))


@pytest.mark.parametrize("node_id", NODES)
def test_the_prompt_advertises_exactly_the_node_allow_list(node_id):
    assert advertised(node_id) == set(NODE_TOOLS.get(node_id, ())), (
        f"{node_id}: the prompt and the allow-list disagree"
    )


@pytest.mark.parametrize("node_id", NODES)
def test_every_advertised_tool_is_actually_registered(node_id, monkeypatch):
    """Catches a tool that exists in neither the registry nor anywhere else."""
    from app.agents.context import GraphContext
    from app.integrations.fixture_source import FixtureSource

    src = FixtureSource()
    ctx = GraphContext(
        tuple(src.events()), tuple(src.evidence()), src.site_model(), src.baseline_kpi()
    )
    registered = {t.tool_name for t in build_read_tools(ctx).values()} \
        if isinstance(build_read_tools(ctx), dict) else {getattr(t, "tool_name", getattr(t, "__name__", "")) for t in build_read_tools(ctx)}
    missing = advertised(node_id) - registered
    assert not missing, f"{node_id} prompt names unregistered tools: {sorted(missing)}"
