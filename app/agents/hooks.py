"""Strands lifecycle hooks: CAIRN's control and telemetry surface.

docs/architecture/03 3.6. Hooks are a control surface, not the only security boundary -
policy and the action gateway remain authoritative. What hooks add here is per-node
enforcement and evidence:

- Before a tool call, the tool name is checked against that node's allow-list and
  cancelled if it is not on it. A read-only specialist cannot reach another node's
  tools, and no agent can reach a state-changing tool because none is registered.
- After a tool call, status, duration and a response hash are recorded, so the audit
  trail shows what the agent actually looked at rather than what it claimed.
- Invocation timings are measured here instead of being estimated.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from strands.hooks import (
    AfterInvocationEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from app.domain.models import ToolCallRecord


def response_hash(payload: Any) -> str:
    try:
        body = json.dumps(payload, sort_keys=True, default=str)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        body = repr(payload)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


@dataclass
class NodeTelemetry:
    """What the hook chain observed for one graph node."""

    node_id: str
    allowed_tools: tuple[str, ...]
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    duration_ms: int = 0
    model_calls: int = 0
    started_at: float | None = None

    @property
    def blocked_tools(self) -> list[ToolCallRecord]:
        return [c for c in self.tool_calls if c.blocked]


class CairnAgentHooks(HookProvider):
    """Per-node hook provider. One instance per agent, one telemetry record per node."""

    def __init__(
        self,
        *,
        node_id: str,
        allowed_tools: tuple[str, ...],
        structured_tool_name: str,
        correlation_id: str,
        telemetry: NodeTelemetry,
    ) -> None:
        self.node_id = node_id
        self.allowed_tools = frozenset(allowed_tools)
        self.structured_tool_name = structured_tool_name
        self.correlation_id = correlation_id
        self.telemetry = telemetry

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self._before_invocation)
        registry.add_callback(BeforeModelCallEvent, self._before_model_call)
        registry.add_callback(BeforeToolCallEvent, self._before_tool_call)
        registry.add_callback(AfterToolCallEvent, self._after_tool_call)
        registry.add_callback(AfterInvocationEvent, self._after_invocation)

    # ------------------------------------------------------------------ invocation

    def _before_invocation(self, event: BeforeInvocationEvent) -> None:
        self.telemetry.started_at = time.perf_counter()
        event.invocation_state["correlationId"] = self.correlation_id
        event.invocation_state["nodeId"] = self.node_id

    def _before_model_call(self, _: BeforeModelCallEvent) -> None:
        self.telemetry.model_calls += 1

    def _after_invocation(self, _: AfterInvocationEvent) -> None:
        if self.telemetry.started_at is not None:
            self.telemetry.duration_ms = int((time.perf_counter() - self.telemetry.started_at) * 1000)

    # ------------------------------------------------------------------ tool calls

    def _is_permitted(self, tool_name: str) -> bool:
        # The structured-output tool is injected by Strands to enforce the typed
        # boundary. It is not a domain tool and is always permitted.
        return tool_name == self.structured_tool_name or tool_name in self.allowed_tools

    def _before_tool_call(self, event: BeforeToolCallEvent) -> None:
        tool_name = event.tool_use.get("name", "")
        if self._is_permitted(tool_name):
            return
        reason = (
            f"{tool_name} is not on the allow-list for node {self.node_id} "
            f"({sorted(self.allowed_tools) or 'no tools'})"
        )
        event.cancel_tool = reason
        self.telemetry.tool_calls.append(
            ToolCallRecord(tool_name=tool_name, status="blocked", blocked=True, reason=reason)
        )

    def _after_tool_call(self, event: AfterToolCallEvent) -> None:
        tool_name = event.tool_use.get("name", "")
        if tool_name == self.structured_tool_name:
            return  # typed boundary plumbing, not a domain observation
        if any(c.tool_name == tool_name and c.blocked for c in self.telemetry.tool_calls):
            return  # already recorded as blocked
        result = event.result or {}
        self.telemetry.tool_calls.append(
            ToolCallRecord(
                tool_name=tool_name,
                status="error" if event.exception or result.get("status") == "error" else "success",
                duration_ms=int((event.duration or 0) * 1000),
                response_hash=response_hash(result.get("content")),
            )
        )
