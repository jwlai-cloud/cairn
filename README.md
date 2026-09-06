# CAIRN

## Mine Operations Decision Fabric

CAIRN is a governed enterprise agent for mining operations. It correlates fragmented operational signals, coordinates specialist analysis, proposes evidence-backed recovery plans, obtains accountable approval, and records the resulting actions and outcomes.

The first vertical slice is **compound-disruption recovery during an open-pit mine shift**, implemented with Python, the Strands Agents SDK, Amazon Bedrock, synthetic mine events, and a simulation-only action gateway.

## Start here

Read the [architecture pack](docs/architecture/README.md), then follow the [Claude Code handoff](docs/architecture/07-claude-code-handoff.md).

## Current boundaries

- No live mine-system credentials.
- No direct control of trucks, crushers, PLCs, safety interlocks, permits, blasts, or isolations.
- State-changing actions require typed policy checks, scoped approval, idempotency, and audit records.
- The model is not the authorization boundary.

## Target workflow

```text
Observe → Correlate → Assess → Generate options → Review policy
        → Obtain approval → Coordinate actions → Verify outcome
```

## Repository status

This repository currently contains the architecture and implementation handoff. The next agent should build the first vertical slice in small, tested increments and keep the architecture pack updated as decisions change.
