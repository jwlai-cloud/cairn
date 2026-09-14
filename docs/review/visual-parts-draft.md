# Visual parts: TOGAF slides, Strands topology, sequence flow

Draft for review. Nothing here is built yet.

## The constraint that shapes all of it

The shipped script is **4:48 against a 5:00 cap**. Twelve seconds spare. So no new
narration section can be added. Anything new is either:

1. a slide that fills narration **already written**, or
2. a silent cutaway under narration already written.

Act 4 already spends 63 seconds pointing at three screens that do not exist. Those are
the TOGAF slides, and they are the priority.

## What exists today

| Artefact | State | In the video? |
|---|---|---|
| Architecture diagram | Built. `docs/architecture/diagrams/cairn-architecture.{svg,png,html}`, in the README. Carries the boundary claim and shows Zone 0 unreachable. | No |
| Strands topology | Only implicit, inside the architecture diagram. No dedicated view of the fan-in or the typed edges. | No |
| Sequence flow | Does not exist. | No |
| TOGAF ADM view | Does not exist. | No, and Act 4 asks for it |
| Traceability chain | Exists as a table in `docs/architecture/09-togaf-adm-artefacts.md` section 9.12. Not a visual. | No, and Act 4 asks for it |

Every beat of the current cut is UI. No diagram appears at any point, which is a gap
against a rubric that rewards showing the technically interesting choices.

## Part A - TOGAF ADM phase view

**Fills:** cue 3:24, hold 24s. Narration is already written and unchanged:

> TOGAF is what helped us turn these controls into an architecture instead of a
> collection of prompts. We started with stakeholder concerns, turned them into
> principles and requirements, mapped those requirements to building blocks, and
> connected each one to a test. It is a chain of accountability, from the question
> someone asks to the behaviour the system must prove.

**Must assert:** the ADM phases A to H plus Requirements Management at the centre, with
the phases this project actually ran marked as run, and the ones it did not marked as
not run. One narrow pass, honestly labelled.

**Question for review:** the narration never says "ADM" or names a phase letter. Should
the slide label phases A to H at all, or should it show only the four moves the
narration names, which are concerns, principles and requirements, building blocks, and
tests? Naming eight phases the voice never mentions may be the same acronym problem in
visual form.

## Part B - the traceability chain

**Fills:** cue 3:48, hold 25s. Narration already written and unchanged:

> Take the safety question on screen. Can CAIRN waive a safety control? The answer
> becomes a principle: no direct control path to operational technology. That becomes a
> requirement: high-consequence actions are denied for every role. It becomes a policy
> service in the architecture, and a test that fails if a model is ever consulted.

**Must assert:** one link revealed per clause, five links total, ending on a green test.
The chain is real and each link resolves to a real artefact in the repo.

Proposed on-screen chain, with the identifiers shown but never spoken:

    a safety authority asks        ->  principle          ->  requirement
    "can it waive a control?"          no OT control path     deny high-consequence
                                                              actions, every role

      ->  building block        ->  implementation      ->  test
          policy service            app/policy/             passes, and fails the
                                    decisions.py            build if a model is called

**Question for review:** the narration says "a test that fails if a model is ever
consulted". Showing the test name makes that checkable, but a test id is exactly the kind
of internal label the review said not to read aloud. Show it on screen and leave it
unspoken, or leave it out entirely?

## Part C - requirements and tests table

**Fills:** cue 4:13, hold 14s. Narration already written and unchanged:

> That discipline even caught an inconsistency in our own synthetic scenario. The shift
> target did not line up with the fleet capacity we had declared. We corrected it before
> it became a misleading demo.

**Must assert:** seventeen requirements, each with the test that proves it, so the single
traced example in Part B is visibly one row of many.

**Problem to solve in review:** the narration on this beat is about the caught
inconsistency, not about the table. The words and the picture are talking about different
things for fourteen seconds. Options:

1. Show the table and let the voice talk over it. Weakest, but no script change.
2. Show the corrected figures instead: the old shift target beside the fleet capacity
   that contradicted it. Matches the words exactly.
3. Split the beat: table for 6s, then the correction for 8s. Costs no runtime.

Option 2 or 3 look better than what is currently specified. Worth a view.

## Part D - Strands topology

**No narration budget.** Act 2's words are already written and already carry the claim:

> We chose Strands because it gives us a practical way to compose these specialists
> without building an uninspectable swarm. Each one returns a structured finding rather
> than a paragraph of text. Evidence, assumptions and uncertainty travel with that
> finding into the next stage.

**Proposal:** a silent cutaway of roughly four seconds inside that 20-second beat,
showing the fan-in. Four specialists in parallel, one planner waiting on all four, typed
edges labelled with what actually crosses them, and the node budget and timeout on the
frame. Then cut back to the live spine.

**Must assert:** the four run in parallel, the planner waits for all four, and the edges
carry structured findings rather than execution order.

**Question for review:** is a four-second silent diagram insert worth it, or does cutting
away from the live UI during the one beat that explains Strands weaken it? The live spine
is already showing real parallel execution with real timings.

## Part E - sequence flow

**No narration budget, and no obvious place.** A sequence diagram is the clearest way to
show the ordering that matters, which is policy, then approval, then the idempotent
claim, with audit written at every stage. That ordering is a real engineering decision:
an earlier version checked the unknown-claim guard after policy and approval, which
returned the wrong error for an expired approval.

**Proposal:** build it for the README and the Devpost page, and keep it out of the video.

If it should be in the video, the honest cost is a script cut. The cheapest candidates:

- cue 2:41, human approval, 19s. Cutting to 12s loses the plan-version binding detail.
- cue 1:58, the three options, 19s. Cutting to 13s loses two of the three trade-offs.

Neither looks worth a sequence diagram. Recommend README and Devpost only.

## Summary of what is being asked

| Part | Build? | Narration | Open question |
|---|---|---|---|
| A, ADM view | Yes | Already written | Label eight phases, or only the four moves the voice names? |
| B, traceability chain | Yes | Already written | Show the test id on screen unspoken, or omit it? |
| C, requirements table | Yes | Already written | Words and picture disagree for 14s. Which of three options? |
| D, Strands topology | Probably | None, silent cutaway | Worth leaving the live UI for four seconds? |
| E, sequence flow | Yes, but not for the video | None | Confirm README and Devpost only. |
