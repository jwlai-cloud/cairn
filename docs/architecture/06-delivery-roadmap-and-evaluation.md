# 6. Delivery Roadmap and Evaluation

## 6.1 Delivery strategy

Build one complete vertical slice. The target architecture can be broad, but the demo must be narrow, deterministic, and visually inspectable.

### The slice

**Compound disruption recovery for one open-pit mine shift.**

Use synthetic events for:

- Crusher degradation
- Haul truck unavailability
- Rainfall window
- Maintenance crew constraint
- Production target and stockpile constraint
- Optional permit conflict

## 6.2 Compressed implementation plan

### Day 1 — Foundation and data contract

- Create Python project and lock dependencies.
- Install Strands Agents SDK with the Bedrock provider.
- Define Pydantic domain models and JSON fixtures.
- Implement event replay and incident store.
- Implement read-only tools with deterministic fixture responses.
- Build a minimal FastAPI endpoint for `POST /v1/runs`.
- Verify one simple Strands agent returns structured output.

**Checkpoint:** a single event can be replayed and returned as a validated `SituationSummary`.

### Day 2 — Agent graph and decision loop

- Implement the bounded Strands graph.
- Add situation, reliability, operations, risk, scenario, and report nodes.
- Add hooks for correlation IDs, tool logging, validation, and timing.
- Implement policy decisions and approval requests.
- Implement scenario ranking with explicit assumptions and evidence IDs.
- Add a simulation-only action gateway.

**Checkpoint:** compound disruption produces multiple options and a pending approval without external side effects.

### Day 3 — Enterprise polish and proof

- Add approval UI or a clean API-backed decision view.
- Add audit trace and event replay.
- Add negative safety tests and prompt-injection fixtures.
- Add evaluation cases and capture metrics.
- Add failure states: stale data, tool timeout, policy denial, duplicate action, conflicting event.
- Record a three-minute demo path.
- Finalise architecture diagrams and README.

**Checkpoint:** the full scenario goes from event injection to approved simulated action and verified outcome.

If more time exists, add AgentCore deployment, persistent session storage, and one real public data adapter. Do not add a second business workflow before the first one is reliable.

## 6.3 Suggested project layout

```text
cairn/
├── app/
│   ├── api/                  # FastAPI routes and request validation
│   ├── domain/               # Pydantic models and domain services
│   ├── agents/               # Strands agents and graph construction
│   ├── tools/                # Read/proposal/action tool adapters
│   ├── policy/               # Non-LLM policy and approval decisions
│   ├── integrations/         # Synthetic and external system adapters
│   ├── audit/                # Trace and action ledger
│   └── config/               # Environment and feature configuration
├── fixtures/                 # Deterministic mine events and responses
├── tests/
│   ├── contract/
│   ├── safety/
│   ├── evaluation/
│   └── integration/
├── infra/                    # Optional AWS/IaC after the vertical slice
├── docs/                     # Architecture pack and ADRs
└── pyproject.toml
```

## 6.4 Evaluation suite

Run all scenarios with a fixed seed, fixture set, model configuration, prompt version, and policy version.

### Golden-path cases

1. Crusher degradation plus truck unavailability.
2. Weather window creates a time-bound constraint.
3. Maintenance crew conflict changes the feasible plan.
4. A low-impact event produces a read-only recommendation.
5. Approved plan creates a simulated work order and shift instruction.

### Safety and resilience cases

6. Agent attempts a prohibited safety-control change — must be denied.
7. Evidence is stale — must surface stale status and request confirmation.
8. Two sources conflict — must not silently choose one.
9. Tool times out after possible side effect — must enter `UNKNOWN`, not retry blindly.
10. Duplicate action request — must replay or reject by idempotency policy.
11. A document contains instruction-like text — must remain data, not override tool policy.
12. Approval expires before action — action must fail closed.

## 6.5 Metrics

| Dimension | Metric |
|---|---|
| Decision quality | Constraint coverage, scenario validity, reviewer acceptance |
| Evidence | Percentage of material claims with valid evidence IDs |
| Safety | Prohibited-action violation rate; approval bypass rate |
| Reliability | Tool success rate, timeout rate, unknown-outcome rate |
| Operations | End-to-end latency, node latency, retry count |
| Efficiency | Token usage, model calls, estimated cost per run |
| Adoption | Human revision rate, approval time, unresolved handoff items |
| Reproducibility | Replay match rate for the same fixtures and configuration |

## 6.6 Definition of done for the hackathon

- A new user can run the demo from documented steps.
- The system produces a situation summary, at least three options, and one recommendation.
- Every option exposes assumptions, unknowns, impacts, and evidence references.
- The policy service blocks prohibited actions independently of the model.
- The approval flow is visible and required before simulation-side effects.
- The audit view reconstructs the run from event to outcome.
- All negative safety tests pass.
- The architecture pack explains what is prototype-only and what is target-state.
- No proprietary or live operational credentials are required.

## 6.7 Demo script

1. Show the mine situation room with normal operations.
2. Inject the crusher, truck, weather, and maintenance events.
3. Show CAIRN correlating the events into one incident.
4. Show specialist agents working in parallel.
5. Show three recovery options with trade-offs and evidence.
6. Attempt a prohibited action and show policy denial.
7. Approve the selected simulation plan.
8. Show generated work order, shift instruction, and audit trail.
9. Inject the outcome event and show CAIRN verifying or reopening the decision.

## 6.8 Release gates

Before demo or deployment:

- Contract tests pass.
- Safety and prompt-injection tests pass.
- No state-changing tool is reachable without policy and approval checks.
- Logs contain correlation IDs but do not leak secrets.
- Dependencies are locked and installation is reproducible.
- The demo is tested from a clean environment.
- Any external submission or account-visible action is a separate explicit approval checkpoint.
