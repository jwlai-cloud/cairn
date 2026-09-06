# Claude Code project instructions

Before implementing code, read:

1. `docs/architecture/README.md`
2. `docs/architecture/07-claude-code-handoff.md`
3. All three ADRs under `docs/architecture/decisions/`

Treat the architecture pack as the current design contract. Do not broaden scope until the compound-disruption vertical slice works end to end.

Use Python and the Strands Agents SDK. Verify the installed Strands API and dependency versions before using them. Use a bounded Strands Graph workflow with deterministic policy and approval services outside the model.

Keep all data synthetic until an explicit decision authorises an external integration. Do not connect to live operational technology or add a direct control path. State-changing tools must remain simulation-only until the approval, policy, idempotency, audit, and safety tests pass.

At each checkpoint, report:

- What changed.
- What was tested.
- What remains simulated or unverified.
- The exact command to reproduce the result.
- The next smallest safe implementation step.
