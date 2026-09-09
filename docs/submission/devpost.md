# CAIRN — Devpost submission copy

Paste-ready. Track: **Professional Agents**. Every number here is measured, and the
limitations section is deliberate: an enterprise-agent claim that hides its boundaries is
the claim a judge distrusts first.

---

## Tagline (one line, ~70 chars)

> A governed decision fabric for mine operations. It recommends. It never authorises.

---

## Inspiration

Eight hours into a twelve-hour shift at an open-pit iron ore mine, four systems are each
about to be completely right, and useless.

Plant control knows the primary crusher has dropped to 75%. Fleet management knows a haul
truck stopped at 14:08. The weather service knows a rain cell closes the main ramp in 42
minutes. The maintenance system knows the only crew is committed elsewhere until 16:10.

Not one of them knows those are the same problem. A supervisor works that out from four
screens, under a closing window, and their name goes on the decision.

The obvious move is to put an agent on it. The obvious risk is that mining is a domain
where a confidently wrong action can hurt someone, and where a duplicate work order is
worse than a slow answer. So the interesting question is not "can an agent reason about
this" — it plainly can — but **what has to be true before anyone would let it near a
shift.** CAIRN is an answer to that second question.

## What it does

**CAIRN correlates fragmented operational signals into one incident, argues the
trade-offs, and then refuses to act until an accountable person signs.** The
differentiator is not the reasoning; it is that the reasoning is structurally incapable
of authorising anything.

1. **Correlate.** Five signals from four source systems become one compound disruption
   with a 42-minute decision window — not five alerts.
2. **Analyse in parallel.** Four specialist agents (situation, reliability, operations,
   risk and HSE) execute concurrently in a bounded Strands graph. Each returns a typed,
   evidence-backed finding rather than prose.
3. **Plan.** A scenario planner waits for all four, then produces three recovery options
   that trade different things away — tonnes, recovery time, equipment protection — each
   with impacts, assumptions, constraints, evidence ids, confidence and the approval it
   would require.
4. **Refuse.** Ask it to override a safety interlock and it is denied by a deterministic
   policy table, with **no model call at all**. There is no prompt that talks past this,
   because no model is in the decision path.
5. **Escalate to a person.** A permitted action still needs a named role. The approval
   token is scoped to those assets, bound to that plan version and evidence set, expiring,
   and good exactly once. Change the plan and the approval is void.
6. **Fail safe when the world is ambiguous.** A dispatch timeout after the call may
   already have applied produces `UNKNOWN`. A blind retry is refused with
   `RECONCILIATION_REQUIRED`. Only authoritative confirmation closes it:
   `UNKNOWN → RECONCILING → SUCCEEDED`.
7. **Leave a record.** The whole decision reconstructs from an append-only ledger: event,
   evidence, findings, policy decision, approval, action, outcome.

The interface makes the boundary literal. The decision loop lists eight stages; the last
three — Policy, Act, Verify — are labelled **`no model`**, because they are deterministic
services and a test fails the build if deciding a high-consequence action ever reaches a
model.

## How we built it

**Orchestration.** AWS Strands Agents SDK 1.54. A bounded `GraphBuilder`: four specialist
agents are entry points, each edged to a single `scenario_planner` that waits for all
four. `max_node_executions=12`. Timeouts are mode-aware — 90s execution / 30s per node
against the fixture provider, 420s / 150s against Bedrock, because a fixture node answers
in milliseconds and a real one takes seconds.

**Typed edges, not pasted text.** Every node's output is a Pydantic v2 contract with
`extra="forbid"`, and Strands enforces it through a forced tool call — client-side tool
calling, not Bedrock structured outputs, which the Claude and Nova model cards list as
unsupported. The edges carry `SituationSummary`, `ConstraintSet`, `ConstraintSet`,
`RiskAssessment`, and the planner emits `ScenarioSet`.

**Governance outside the graph.** Policy (`app/policy/decisions.py`), the approval
service, the action gateway and the audit ledger all sit outside the Strands graph. Every
state change passes through one gateway in one order: unknown-claim check, then policy,
then approval, then an idempotent claim, then a simulation-only external call. There is
no second path.

**Tool discipline.** Each node has an allow-list, and a Strands `HookProvider` cancels any
call outside it at call time. Every specialist must gather evidence through a tool before
answering.

**Two modes, one graph.** `fixture` is a deterministic Strands `Model` provider: zero
credentials, byte-identical replay, and it is what CI and the 13-case evaluation suite run
against. `bedrock` runs a real model. Both execute the same graph and the same governance —
swap the brain, the safety envelope does not move.

**Live progress.** Per-node start and stop events stream over newline-delimited JSON, so
the decision loop fills while the graph is running. Against a real model that is fifteen
seconds of visible parallel work rather than a motionless page.

**Method.** The architecture was developed as a TOGAF ADM cycle used as a lens on one
increment: 6 principles, 17 architecture requirements each traced to a verification, 8
solution building blocks. One worked chain, end to end — an HSE authority asks "can this
waive a safety control?" → principle PR-05, no direct control path to operational
technology → requirement AR-05, deny every Tier 4 action for every role → building block
SBB-04, the deterministic policy service → `app/policy/decisions.py` → a test that fails
the build if a model is consulted.

## Challenges we ran into

**The graph edges were decorative.** An early version looked correct and was not: deleting
every hazard from the input left the plan unchanged, because the planner was not reading
its dependencies' output. An evaluation case caught it. The fixture model provider now
parses the upstream transport and raises `UpstreamParseError` if a declared dependency is
missing, so a graph whose edges do nothing cannot pass.

**The fixture was hiding a loose contract.** Every field a real model got wrong had been
correct for months, because the fixture always wrote the right value. `key` was a `str`
with its three legal values in a code comment, so `option_1` validated exactly as well as
`recover_tonnes`. `required_approvals` was `list[str]`, so a model could name a role the
approval service cannot resolve. `recommended_scenario_id` was a `str`, so it could point
at nothing — and did. The tonnes sign convention was never stated anywhere, so the model
read it as a loss and returned negatives for every option. All four are now enum,
enum, model-validator and field description, with five provider-invariance tests that fail
against the loose version. A constraint the schema does not carry is one the model is
never told about.

**A guard that guarded one door.** The demo asserts on screen that the policy path never
invokes a model. The test making that claim patched a single seam, so a direct model
construction inside policy would have passed it while the video said otherwise. It now
patches three, and was verified by making the policy service construct one:
`AssertionError: policy must not construct a model`.

**The reliability semantics were in the wrong order.** The unknown-claim check ran after
policy and approval, so an expired approval on an in-doubt action returned
`APPROVAL_EXPIRED` instead of `RECONCILIATION_REQUIRED` — the wrong refusal, and the one
that invites a retry.

**Documentation that lied to the model.** Three prompts advertised tools that do not
exist. `get_active_permits` and `simulate_recovery_plan` are fictional; the planner was
offered two functions that run deterministically after the graph while its allow-list is
empty by design. Fixture mode never reads prompts, so only a real model could hit it. Two
guards now assert that a prompt's advertised tools equal its node's allow-list.

## Accomplishments that we're proud of

- **126 tests. 13 of 13 evaluation cases. Zero prohibited-action violations, zero approval
  bypasses.** The evaluation cases are deterministic assertions, not LLM-judged scores,
  because "was the Tier 4 action denied?" has a right answer — and judging it with a model
  would put a model back into the assurance path.
- **A real model runs the real graph.** `us.amazon.nova-lite-v1:0` completes all five
  nodes in 13–17 seconds, every node satisfying its typed contract, every specialist
  calling tools before answering. Measured: 30,253 input and 2,504 output tokens per run.
- **The safety envelope is provider-independent.** The same policy table, approval service
  and gateway ordering hold in both modes, and the tests that prove it need no credentials.
- **`UNKNOWN` is a first-class outcome.** Most agent demos show the happy path. This one
  shows the call that may already have applied, the retry that is refused, and the
  reconciliation that closes it.
- **Every requirement traces to a passing test.** Seventeen of them, in a table, with the
  test id beside each.
- **The method found real defects.** A compliance review caught a shift target a quarter of
  what the declared fleet and crusher could move. Requirements traceability caught invented
  survey elevations in a system whose whole claim is that it does not invent numbers.

## What we learned

**The fixture that makes a demo reproducible is also the thing that hides its bugs.**
Every defect a real model exposed had been latent and green for the entire project. Not
because the tests were weak, but because they asserted against a provider that always
behaved. The lesson is narrower and more useful than "test more": *anything whose
correctness depends on a provider must be asserted against the schema, not the provider.*

**A comment is not a constraint.** `key: str  # protect_safety | recover_tonnes |
preserve_equipment` reads like a specification and enforces nothing. The model never sees
the comment; it sees the JSON schema. If a rule matters, it has to live where the machine
looks.

**Deterministic beats clever in the assurance path.** The most persuasive moment in the
demo is a table lookup. There is no prompt engineering to defend, nothing to jailbreak,
and the reason it convinces is precisely that no model is involved.

**Read the SDK, not its docstring.** `Graph.stream_async` documents its events as
`multi_agent_node_start`. They are actually `multiagent_node_start`. Parsing the documented
shape produced no progress and no error — the graph ran perfectly and reported nothing,
which is the worst kind of wrong.

## What's next

- **Live progress into the audit.** Node transitions stream to the browser but are not yet
  ledger entries; a reconstructable decision should include when each stage started.
- **Real identity.** Roles come from configuration. The approval service is shaped for an
  IdP and does not have one, and "accountable human" means little until it does.
- **Second scenario.** Slope instability with a permit conflict, exercising the
  `PERMIT_CONFLICT` event type the model layer already understands.
- **Reasoning quality, measured.** The evaluation suite proves safety and integrity, and
  says nothing about whether the incident brief is any good. That is the honest case for
  an LLM-judged layer — beside the deterministic gate, never inside it.
- **Provider matrix.** The provider-invariance claim deserves a second vendor. Anthropic
  models are pending a use-case form on this account, and GPT-5.6 Luna is not available
  to it, so the claim is currently demonstrated against one real provider rather than two.

## What this is not

Stated plainly, because an enterprise-agent submission that hides its boundaries invites
exactly the scepticism it should be dispelling.

- **Simulation only, with no operational certification.** Every event, asset and artefact
  is synthetic. No mine system, PLC, SCADA, dispatch, ERP or CMMS is connected. There is
  no control path, by design — the architecture draws Zone 0 as unreachable.
- **The option economics are illustrative fixtures**, internally consistent but not a
  modelled mine plan.
- **Determinism is a fixture-mode property.** Evaluation case EV-13 asserts identical
  replay, and that is true of the fixture provider. A real model varies run to run, and
  Nova Lite chose differently on consecutive runs.
- **It does not replace** fleet management, plant control, ERP, CMMS or a MineRP-class
  platform. It connects them when a decision crosses their boundaries.

## Built with

`python` · `aws` · `amazon-bedrock` · `strands-agents` · `amazon-nova` · `fastapi` ·
`pydantic` · `three.js` · `sqlite` · `uv` · `github-actions` · `docker` · `togaf`

---

# Where each piece goes

| Devpost field | Source |
|---|---|
| Project name | CAIRN |
| Tagline | The one-liner above |
| Story sections | Inspiration through Built with, in order |
| Track / category | **Professional Agents** |
| Repository | https://github.com/jwlai-cloud/cairn (public, Apache-2.0 at repo root) |
| Architecture image | `docs/architecture/diagrams/cairn-architecture.png` |
| Demo video | YouTube, public or unlisted, under 5:00 |
| Testing link | The App Runner URL, free access through 2026-10-08 |
| AWS Builder ID | Yours — required on the form |

## Not yet done

These are hard requirements, not polish. Judging is gated on them before scoring starts.

1. **Upload the video to YouTube** as public or unlisted, and confirm it plays logged out.
2. **Deploy for the testing link.** `Dockerfile` is verified: 258MB, non-root uid 10001,
   `/healthz`, `exec` so uvicorn is PID 1 and SIGTERM stops it in one second. App Runner at
   0.25 vCPU / 1 GB is roughly $6/month.
3. **Put the Builder ID on the form.**
4. **Decide the hosted mode.** Fixture needs no credentials and replays identically;
   Bedrock proves a real model runs but needs an instance role and costs per click. A
   sensible default is Bedrock with a per-session rate limit falling back to fixture, and
   the header naming whichever actually ran.

## Consistency check before submitting

The written story, the diagrams and the video must carry the same numbers. Current values:

- 126 tests, 13 of 13 evaluation cases
- 17 architecture requirements, 6 principles, 8 solution building blocks
- Nova Lite: 13–17s per graph run, 30,253 input / 2,504 output tokens
- Fixture graph: about 232ms end to end
- Zero prohibited-action violations, zero approval bypasses
