"""Deterministic Strands model provider.

Why this exists: the visual demo must run on a clean checkout with no AWS credentials
and must replay byte-identically, but the agent layer must still be a real Strands
Agent/Graph rather than a hand-rolled loop. FixtureModel implements the Strands `Model`
interface and returns a pre-computed structured payload, so the graph topology,
structured-output enforcement and node boundaries are all genuinely exercised.

What this does NOT exercise: Strands hooks (not yet implemented) and tool invocation
(no agent is registered with tools yet). See docs/architecture/03 3.5-3.6.

Swapping in `strands.models.BedrockModel` is a one-line change in graph.py; nothing else
about the workflow moves.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from pydantic import BaseModel
from strands.models import Model

from app.domain.models import MODEL_ID_FIXTURE


class FixtureModel(Model):
    """Returns one canned, schema-valid payload for the node it is attached to."""

    def __init__(self, payload: BaseModel, *, node_id: str) -> None:
        self._payload = payload
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

    async def structured_output(
        self, output_model: type[BaseModel], prompt: list[dict], system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"output": self._payload}

    async def stream(
        self,
        messages: list[dict],
        tool_specs: list[dict] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict[str, Any]]:
        # Strands enforces structured output by forcing a tool call. Satisfy that
        # contract directly so the agent's typed boundary is exercised, not bypassed.
        yield {"messageStart": {"role": "assistant"}}
        if tool_specs:
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"name": tool_specs[0]["name"], "toolUseId": f"fixture-{id(self)}"}}
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": self._payload.model_dump_json(by_alias=True)}}}}
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
