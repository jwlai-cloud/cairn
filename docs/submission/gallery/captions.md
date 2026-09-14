# Gallery captions

Upload in this order. Image 1 becomes the thumbnail, so it leads with the differentiator
rather than with scene-setting.

Each caption states a claim the image actually evidences. Nothing here describes something
the frame does not show.

---

**1 · `06-policy-denied.jpg`**

> Ask it to override a safety interlock and it is denied by a policy table, with no model
> call at all. The model is not in this decision path, so there is no prompt that talks
> past it.

**2 · `01-room-normal-shift.jpg`**

> Eight hours into a twelve-hour shift. 16,900 t against a 28,000 t target, eight trucks,
> no alerts. The header names the model actually running: Amazon Nova Lite on Bedrock.

**3 · `02-spine-parallel.jpg`**

> The decision loop mid-run. Four specialists work concurrently and the planner waits for
> all four. The milliseconds are measured by a hook chain, not estimated.

**4 · `03-strands-fan-in.jpg`**

> The bounded Strands graph. Four agents fan in to one planner, and every edge carries a
> typed contract — SituationSummary, ConstraintSet, RiskAssessment — rather than pasted
> text.

**5 · `04-evidence-honest.jpg`**

> It does not tidy up bad inputs. Truck 204's telemetry is fifteen minutes old and is
> marked stale. Two weather sources disagree and both readings are kept.

**6 · `05-three-options.jpg`**

> Three recovery options that trade different things away, each carrying impact, recovery
> time, residual safety risk, confidence, evidence ids and the approval it would require.

**7 · `07-scoped-approval.jpg`**

> A permitted action still needs a person. The token is scoped to those assets, bound to
> this plan version and evidence set, expiring, and good exactly once. Change the plan and
> the approval is void.

**8 · `08-unknown-outcome.jpg`**

> Dispatch timed out after the call may already have applied. The outcome is held UNKNOWN
> and a blind retry is refused, because a duplicate work order is worse than a slow answer.

**9 · `09-architecture-boundary.jpg`**

> Everything inside the dashed boundary is the Strands graph, and that is the only part a
> language model touches. Policy, approval, the action gateway and the audit ledger sit
> outside it.

**10 · `10-zone-zero-unreachable.jpg`**

> The systems a mine actually runs on are drawn unreachable, because they are. There is no
> control path to operational technology at all. Every artefact is simulation-only.

**11 · `11-togaf-traceability.jpg`**

> One stakeholder concern carried to a passing test: can this waive a safety control? →
> principle → requirement → building block → the file → the test. The same chain exists
> for all 17 requirements.

**12 · `12-audit-chain.jpg`**

> The whole decision reconstructs from an append-only ledger: tool calls, agent findings,
> stale and conflicting evidence, the options proposed, the policy decision, the approval,
> the action and its outcome.
