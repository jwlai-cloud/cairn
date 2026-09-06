# 7. Claude Code Handoff

## Mission

Implement the first CAIRN vertical slice: **compound disruption recovery for an open-pit mine shift** using Python, Strands Agents SDK, Amazon Bedrock-compatible model configuration, synthetic fixtures, typed contracts, bounded orchestration, and a simulation-only action gateway.

Read these documents before writing implementation code:

1. `01-architecture-vision.md`
2. `02-target-architecture.md`
3. `03-strands-agent-design.md`
4. `04-security-governance-and-safety.md`
5. `05-interfaces-and-data-contracts.md`
6. `06-delivery-roadmap-and-evaluation.md`
7. `decisions/ADR-001-python-strands-bedrock.md`
8. `decisions/ADR-002-bounded-graph-orchestration.md`
9. `decisions/ADR-003-human-gated-actions.md`

## Implementation order

1. Inspect the installed Python and AWS/Strands versions; do not assume undocumented SDK APIs.
2. Create `pyproject.toml`, lock dependencies, and a reproducible setup command.
3. Implement domain models and fixtures before agent prompts.
4. Implement deterministic event replay and read-only tools.
5. Implement the bounded Strands graph with structured outputs.
6. Add hooks for correlation, tool validation, audit, and timing.
7. Implement the non-LLM policy service and approval records.
8. Implement simulation-only state-changing tools with idempotency.
9. Add API endpoints and a simple situation/approval view.
10. Add safety, contract, replay, and failure tests.
11. Run the clean-environment demo and update the README with exact commands.

## Non-negotiable engineering rules

- Do not use LangGraph, CrewAI, or an unbounded custom loop; use Strands for the agent layer.
- Do not make the model the authorization or safety boundary.
- Do not connect to live mine systems or require proprietary credentials.
- Do not add a tool that directly controls operational technology.
- Keep read, proposal, and state-changing tools separate.
- Require typed structured outputs at every agent boundary.
- Use synthetic data with deterministic seeds for the demo and evaluation.
- Propagate `correlationId`, `siteId`, `actorId`, evidence IDs, and policy version.
- Every state-changing request must use an idempotency key and an approval token.
- Treat all external responses and documents as untrusted data.
- Fail closed when policy, authorization, evidence validation, or approval is unavailable.
- Keep implementation comments focused on why a constraint exists.

## Suggested first user prompt for Claude Code

```text
You are implementing CAIRN, a governed mine-operations decision fabric.

Start by reading all files under outputs/cairn-architecture. Treat them as the architecture contract. Build only the first vertical slice: compound disruption recovery for one open-pit mine shift using synthetic fixtures.

Use Python and the installed Strands Agents SDK. Verify the current SDK APIs from the official documentation or installed package before coding. Use a bounded Strands Graph workflow with deterministic policy and approval services outside the model. Do not use LangGraph or a free-form swarm.

First inspect the environment and propose the smallest implementation sequence. Then implement domain models, fixture replay, read-only tools, the graph, structured outputs, policy decisions, simulation-only actions, audit records, and tests. Keep every tool contract typed. Do not connect to live operational systems or allow direct OT control.

Stop after each coherent vertical slice, run the relevant tests, and report what is verified versus still mocked. Do not expand the scope until the end-to-end simulated scenario works.
```

## Expected first implementation artefacts

- `pyproject.toml` with locked or reproducible dependencies.
- `app/domain/models.py` with the contracts in `05-interfaces-and-data-contracts.md`.
- `app/agents/graph.py` with bounded graph construction.
- `app/agents/prompts/` with versioned specialist prompts.
- `app/tools/read_tools.py`, `proposal_tools.py`, and `action_tools.py`.
- `app/policy/decisions.py` with deterministic approval requirements.
- `app/audit/ledger.py` with append-only run/action records.
- `fixtures/scenarios/compound-disruption.json`.
- `tests/safety/` with prohibited-action, stale-data, prompt-injection, duplicate-action, and approval-expiry cases.
- `docs/` copied or linked to this architecture pack.
- Exact local run, test, and demo commands in the project README.

## Completion report format

When handing work back, report:

1. What was implemented.
2. What remains mocked or simulated.
3. Tests run and their results.
4. Strands/AWS versions and model configuration.
5. Known risks or unverified assumptions.
6. Exact command to run the demo.
7. The next smallest safe slice.

## Official references

- [Strands Python quickstart](https://strandsagents.com/docs/user-guide/quickstart/python/)
- [Strands Graph pattern](https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/)
- [Strands hooks](https://strandsagents.com/docs/user-guide/concepts/agents/hooks/)
- [Strands session management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/)
- [Amazon Bedrock provider for Strands](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/)
- [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
