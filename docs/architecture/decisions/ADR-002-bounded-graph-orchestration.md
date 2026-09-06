# ADR-002: Use bounded graph orchestration for the operational path

## Status

Accepted for the first vertical slice

## Date

2026-09-06

## Context

Mining operations have high-consequence workflows and require inspectable decision paths. CAIRN needs parallel specialist analysis, aggregation, policy review, approval, action, and outcome verification. An unconstrained supervisor or swarm would make execution harder to reason about and evaluate.

## Decision

Use a deterministic Strands Graph for the primary recovery workflow:

```text
normalise → specialist analysis in parallel → scenario planning
          → policy review → human approval → action → verification
```

Configure maximum steps, overall timeout, per-node timeout, explicit tool allow-lists, and a bounded revision loop.

## Alternatives considered

### Free-form supervisor loop

Rejected for the first release. It may be useful for exploration, but it makes safety boundaries, reproducibility, cost, and failure behaviour harder to demonstrate.

### Swarm handoffs

Rejected as the primary path. Handoffs can be introduced for lower-risk investigative workflows after the fixed operational path has evaluation coverage.

### Step Functions-only orchestration

Rejected as the first implementation because the agent graph needs local rapid iteration. Step Functions remains a possible cloud control-plane implementation for long-running production workflows.

## Consequences

### Positive

- Parallel analysis without losing a visible execution plan.
- Explicit dependencies and typed node outputs.
- Easy replay, timeout, failure, and evaluation controls.
- Clear mapping to enterprise workflow governance.

### Negative

- Less flexible than a fully dynamic agent swarm.
- The graph must be versioned as a business process.
- Complex branching requires deliberate schema and test design.

## Exit condition

Revisit this decision only after the fixed graph passes the evaluation suite and a concrete use case demonstrates that dynamic orchestration adds value without weakening controls.
