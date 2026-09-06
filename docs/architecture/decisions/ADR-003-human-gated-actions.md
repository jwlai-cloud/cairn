# ADR-003: Require human-gated state-changing actions

## Status

Accepted

## Date

2026-09-06

## Context

CAIRN operates in a mining context where actions can affect production, workers, contractors, safety controls, equipment, environmental obligations, and external stakeholders. Model output is probabilistic and cannot serve as the authorization boundary.

## Decision

All state-changing actions must pass:

1. Typed input validation.
2. Identity and role authorization.
3. Deterministic policy evaluation.
4. Explicit human approval where required.
5. Scoped, expiring approval token.
6. Idempotency and expected-version checks.
7. Action gateway execution.
8. Outcome reconciliation and audit recording.

Safety-critical control changes, permit approvals, blast decisions, isolations, emergency instructions, and direct OT actuation are prohibited from the MVP.

## Alternatives considered

### Fully autonomous action execution

Rejected because it creates unacceptable safety, assurance, and accountability risk for the prototype and would require a separate certified control and assurance programme.

### Human approval inside the prompt only

Rejected because prompt instructions are not an enforceable authorization boundary.

### Draft-only system

Rejected as the complete target because an enterprise agent must demonstrate a controlled path from insight to action. The MVP uses a simulation-only action gateway to prove the pattern safely.

## Consequences

### Positive

- Clear accountability and explainable decision rights.
- Safe demonstration of enterprise agent behaviour.
- Action replay and reconciliation become first-class capabilities.
- Future automation can be introduced by changing policy tiers, not rewriting the entire agent.

### Negative

- More workflow steps and UI complexity.
- Approval latency may reduce theoretical automation speed.
- Requires an action ledger and policy service from the beginning.
