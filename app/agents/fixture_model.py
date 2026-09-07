"""Deterministic Strands model provider.

Why this exists: the visual demo must run on a clean checkout with no AWS credentials
and must replay byte-identically, but the agent layer has to be a real Strands
Agent/Graph rather than a hand-rolled loop. `FixtureModel` implements the Strands
`Model` interface, so graph topology, structured-output enforcement and node boundaries
are genuinely exercised.

Critically, this is **not a constant**. Strands' `Graph` delivers each upstream node's
structured output to its dependants as JSON in the request messages. `FixtureModel`
parses that transport and hands it to a reducer, so a downstream node's output is a
real function of what its dependencies produced. Corrupt an upstream finding and the
plan changes - `tests/evaluation/test_graph_dataflow.py` asserts exactly that.

What this does NOT exercise: Strands hooks (not yet implemented) and tool invocation
(no agent is registered with tools yet). See docs/architecture/03 3.5-3.6.

Swapping in `strands.models.BedrockModel` is a one-line change in graph.py.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any, Callable

from pydantic import BaseModel
from strands.models import Model

from app.domain.models import MODEL_ID_FIXTURE

# Strands' Graph renders upstream results into the dependant node's prompt as
# "\nFrom <node_id>:" followed by "  - Agent: <json>". Parsing that is how a fixture
# node reads its dependencies rather than ignoring them.
_FROM_NODE = re.compile(r"^\s*From (?P<node>[A-Za-z0-9_\-]+):\s*$")
_AGENT_PAYLOAD = re.compile(r"^\s*-\s*Agent:\s*(?P<payload>\{.*\})\s*$", re.DOTALL)


class UpstreamParseError(RuntimeError):
    """Raised when a dependant node cannot read a dependency it was promised."""


def parse_upstream(messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Extract `{node_id: structured_output_dict}` from a Strands graph prompt."""
    found: dict[str, dict[str, Any]] = {}
    current: str | None = None
    for message in messages:
        for block in message.get("content", []) or []:
            text = block.get("text")
            if not text:
                continue
            node_match = _FROM_NODE.match(text)
            if node_match:
                current = node_match.group("node")
                continue
            payload_match = _AGENT_PAYLOAD.match(text)
            if payload_match and current:
                try:
                    found[current] = json.loads(payload_match.group("payload"))
                except json.JSONDecodeError as exc:  # pragma: no cover - transport change
                    raise UpstreamParseError(f"upstream payload from {current} was not JSON") from exc
    return found


class FixtureModel(Model):
    """Runs a deterministic reducer over the node's real upstream inputs."""

    def __init__(
        self,
        reducer: Callable[[dict[str, dict[str, Any]]], BaseModel],
        *,
        node_id: str,
        structured_tool_name: str,
        requires: tuple[str, ...] = (),
        tool_plan: tuple[tuple[str, dict[str, Any]], ...] = (),
    ) -> None:
        self._reducer = reducer
        self._requires = requires
        self._structured_tool_name = structured_tool_name
        # Read tools this node calls before it answers. Without this the tool registry,
        # the allow-list hook and the tool-execution loop would never actually run.
        self._tool_plan = tool_plan
        self._config: dict[str, Any] = {
            "model_id": MODEL_ID_FIXTURE,
            "node_id": node_id,
            "temperature": 0.0,
            "deterministic": True,
        }

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    def _resolve(self, messages: list[dict[str, Any]]) -> BaseModel:
        upstream = parse_upstream(messages)
        missing = [node for node in self._requires if node not in upstream]
        if missing:
            # Fail loudly. A silent fallback here is exactly how a graph starts looking
            # connected while the nodes quietly ignore each other.
            raise UpstreamParseError(
                f"node {self._config['node_id']} did not receive required upstream: {missing}"
            )
        return self._reducer(upstream)

    async def structured_output(
        self, output_model: type[BaseModel], prompt: list[dict], system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"output": self._resolve(list(prompt))}

    def _tool_calls_completed(self, messages: list[dict]) -> int:
        """How many of this node's planned read-tool calls already have results."""
        prefix = f"cairn-{self._config['node_id']}-"
        done = 0
        for message in messages:
            for block in message.get("content", []) or []:
                result = block.get("toolResult")
                if result and str(result.get("toolUseId", "")).startswith(prefix):
                    done += 1
        return done

    async def stream(
        self,
        messages: list[dict],
        tool_specs: list[dict] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict[str, Any]]:
        completed = self._tool_calls_completed(messages)
        if tool_specs and completed < len(self._tool_plan):
            # Gather evidence first, exactly like a real model would, so the hook chain
            # and the node allow-list are exercised on every run.
            name, tool_input = self._tool_plan[completed]
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "start": {
                        "toolUse": {
                            "name": name,
                            "toolUseId": f"cairn-{self._config['node_id']}-{completed}",
                        }
                    }
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(tool_input)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            yield {
                "metadata": {
                    "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                    "metrics": {"latencyMs": 0},
                }
            }
            return

        payload = self._resolve(messages)
        yield {"messageStart": {"role": "assistant"}}
        if tool_specs:
            # Strands enforces structured output by forcing a tool call. Satisfy that
            # contract directly so the agent's typed boundary is exercised, not bypassed.
            yield {
                "contentBlockStart": {
                    "start": {
                        "toolUse": {
                            "name": self._structured_tool_name,
                            "toolUseId": f"fixture-structured-{id(self)}",
                        }
                    }
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": payload.model_dump_json(by_alias=True)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": "structured output unavailable"}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }
