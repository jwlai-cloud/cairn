"""Bedrock smoke test.

Runs one real graph invocation against a real model and reports, per node, whether the
typed contract actually held. This is the check that turns "the architecture is
provider-neutral" from a claim into an observation.

    CAIRN_BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0 python -m app.agents.smoke
    python -m app.agents.smoke --model us.anthropic.claude-sonnet-5

Exit code is non-zero if any node failed to produce a valid typed output, so this can
be wired into a release check once model access exists.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from app.agents.context import GraphContext
from app.agents.graph import PLANNER, SPECIALISTS, run_graph
from app.integrations.fixture_source import FixtureSource

# Per 1M tokens, USD, us-east-1 standard tier. Illustrative: confirm against
# https://aws.amazon.com/bedrock/pricing/ before quoting these to anyone.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "gpt-5.6-luna": (0.22, 1.32),
}


def _price_for(model_id: str) -> tuple[float, float] | None:
    return next((p for family, p in PRICES.items() if family in model_id), None)


async def run(model_id: str | None) -> int:
    if model_id:
        os.environ["CAIRN_BEDROCK_MODEL_ID"] = model_id

    source = FixtureSource()
    ctx = GraphContext(
        tuple(source.events()), tuple(source.evidence()), source.site_model(), source.baseline_kpi()
    )

    started = time.perf_counter()
    result = await run_graph("Compound disruption on Shift A at North Pit.", ctx, mode="bedrock")
    elapsed = time.perf_counter() - started

    print(f"model: {result.model_id}")
    print(f"wall clock: {elapsed:.1f}s\n")
    print(f"  {'NODE':<18} {'STATUS':<10} {'TOOLS':<7} CONTRACT")
    failures = 0
    for spec in (*SPECIALISTS, PLANNER):
        output = result.outputs.get(spec.node_id)
        telemetry = result.telemetry.get(spec.node_id)
        tools = len(telemetry.tool_calls) if telemetry else 0
        if output is None:
            failures += 1
            print(f"  {spec.node_id:<18} {'FAILED':<10} {tools:<7} no typed output")
            continue
        # The contract held only if the payload validates as the declared model.
        valid = isinstance(output, spec.output_model)
        failures += 0 if valid else 1
        print(
            f"  {spec.node_id:<18} {'ok' if valid else 'WRONG TYPE':<10} {tools:<7} "
            f"{spec.output_model.__name__} confidence={getattr(output, 'confidence', '?')}"
        )

    planner = result.outputs.get(PLANNER.node_id)
    if planner is not None:
        print(f"\n  options: {[o.key for o in planner.options]}")
        print(f"  recommended: {planner.recommended_scenario_id}")

    tokens_in = result.usage.get("inputTokens", 0)
    tokens_out = result.usage.get("outputTokens", 0)
    if tokens_in or tokens_out:
        print(f"\n  tokens: {tokens_in:,} in / {tokens_out:,} out")
        price = _price_for(result.model_id)
        if price:
            cost = tokens_in / 1e6 * price[0] + tokens_out / 1e6 * price[1]
            print(f"  estimated cost: ${cost:.4f} for this run")

    print(f"\n  {'PASS' if not failures else f'FAIL ({failures} node(s))'}")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one CAIRN graph against a real Bedrock model.")
    parser.add_argument("--model", help="Bedrock model or inference profile id")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.model))
    except Exception as exc:
        print(f"smoke test failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
