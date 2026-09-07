# Narration cue sheet

Runtime **4:30** against a 5:00 cap. Eighteen cues, 831 spoken words,
30 seconds of headroom.

## What changed, and why

An earlier cut ran 4:48 with only 681 words in it, which left **49 seconds of silence**
spread across fifteen beats and a delivery slow enough to notice. It also never showed
the architecture, which is the strongest artefact in the repository and the one thing a
judge on an agent track will look for.

Both are fixed by the same arithmetic. Raising the rate recovered forty seconds of
speech, and tightening every hold to its own line plus a fixed pad recovered the rest.
That paid for a sixty-second architecture section without going over the cap.

Holds are computed, not chosen: each is its line's length at the measured delivery rate
plus 1.8 seconds.

Holds are not modelled from a word count. That was tried and guessed wrong twice: `say`
does not deliver its nominal rate, the error is not a constant factor, and a word count
cannot predict where a line pauses. `-r 160` gives about 164 effective words per minute
and `-r 185` only 170, so raising the rate between those two buys almost nothing.

Instead `python3 captures/narrate.py --calibrate` speaks every line, measures it, and
prints the hold it needs. Those measurements are the holds in this table, each its line
plus a 1.5 second gap. Re-run it after any wording change.

## The three sources

`Source` says where a cue is filmed. `app` is the live situation room, `slide` is the
deck in `docs/design/slides.html`. The slide cues are contiguous, so `edit.sh` assembles
three sections: app, slides, app.

The architecture cues sit at the head of Act 4 rather than before the refusals. Showing
the behaviour first and the structure second means the boundary is something the viewer
has already watched hold, rather than a claim they are asked to accept up front.

## How to read the table

`Screen` is what the capture must show. `Highlight` names the element a capture-only
overlay must ring while dimming the rest. `narrate.py` reports any line that overruns its
beat; when one does, cut a sentence rather than speaking faster.

## Craft rules applied

- Replace an em dash with a new sentence. Use periods, not semicolons.
- Say who does what. One thought per sentence. Split anything over about 25 words.
- Be specific rather than sterile. Cut every word that does no work.
- Never read a component name, rule identifier or test id aloud. Those go on screen.
- Do not manufacture tension. The forty-two minutes is in the fixture.

## Act 1 - a supervisor, four screens, forty-two minutes

| Cue | Hold | Source | Screen | Highlight | Narration |
|---|---|---|---|---|---|
| 0:00 | 17s | app | Normal shift. Trucks move through the pit. CAIRN visible but quiet. | - | This is CAIRN. In a mine shift, the difficult decisions rarely come from one alarm. They happen when several changes arrive together, across different systems, and nobody has time to assemble the whole picture. CAIRN brings those signals together, tests the options, and helps a supervisor recover the shift safely. |
| 0:17 | 16s | app | Crusher, truck and weather events land. Timeline begins. | `#timeline` | Everything in this demo is synthetic, but the situation is familiar. The crusher is running at seventy-five percent. A haul truck has stopped. Rain will close the main ramp in forty-two minutes. Each source knows one fact. CAIRN sees one operational problem, and a decision window that is already closing. |
| 0:33 | 17s | app | The decision spine on the left | `.spine` | That is the idea behind the spine on the left. It is the decision loop: understand the situation, work out the choices, check the risks, then decide and verify. You can also see where the AI stops. Agents help interpret evidence. Policy, approval and execution stay deterministic and accountable. |
| 0:50 | 16s | app | Four signals arrive. Strands graph starts. Specialists run in parallel. | `.spine` | Five signals arrive from four source systems. CAIRN correlates them into one incident and starts a bounded Strands workflow. Operations, reliability, risk and scenario planning work in parallel, so the decision does not wait on handovers. The graph gives the work clear limits and a clear result. |

## Act 2 - the decision, made visible

| Cue | Hold | Source | Screen | Highlight | Narration |
|---|---|---|---|---|---|
| 1:06 | 17s | app | Specialist nodes complete with measured durations | `.spine` | We chose Strands because it gives us a practical way to compose these specialists without building an uninspectable swarm. Each one returns a structured finding rather than a paragraph of text. Evidence, assumptions and uncertainty travel with that finding into the next stage. That makes the reasoning testable, and easier to trust. |

## Act 3 - evidence, options, and the three stages that refuse

| Cue | Hold | Source | Screen | Highlight | Narration |
|---|---|---|---|---|---|
| 1:23 | 13s | app | Agent cards complete. Stale telemetry and conflicting sources highlighted. | `#evidenceList` | CAIRN also refuses to make messy data look clean. This truck signal is fifteen minutes old, so it is marked stale. The weather sources disagree, so both readings stay visible. It can reason, but it cannot turn uncertainty into fact. |
| 1:36 | 15s | app | Three scenario cards. Select the recommended plan, animate its route. | `#scenarioCards` | Here are the recovery choices. One protects safety and accepts lower production. One recovers more tonnes using the stockpile buffer. The third protects the crusher and gives maintenance room to work. The point is not a clever answer. It is a visible trade-off with evidence behind it. |
| 1:51 | 15s | app | Attempt the interlock override. Hold the denial. Pause. | `#toast` | Now we reach the boundary between intelligence and authority. I will ask for an interlock override. The request is denied by a deterministic policy service before it can become an action. The model may explain a situation or suggest a plan. It does not get to waive a safety control. |
| 2:06 | 12s | app | Approval request. Named role, plan version, scoped assets. Approve. | `#toast` | For an allowed recovery plan, the system still asks for a person. The approval is tied to the named role, the selected assets and this exact plan version. It expires, it can be used once, and it leaves a record. |
| 2:18 | 18s | app | Simulate dispatch timeout. Unknown state, then reconciliation. | `#toast` | Then the outside world behaves the way it sometimes does. Dispatch times out after the call may already have applied. CAIRN does not blindly try again. It marks the result unknown and reconciles it against authoritative state. Only when the outcome is confirmed does the work close. Avoiding a duplicate action can matter as much as the original recommendation. |

## Act 4 - the architecture, and what TOGAF changed

| Cue | Hold | Source | Screen | Highlight | Narration |
|---|---|---|---|---|---|
| 2:36 | 16s | slide | Architecture, wide. The graph boundary drawn dashed. | the dashed graph boundary | This is the whole system on one page. Everything inside the dashed boundary is the Strands graph: four specialists and a planner. That is the only part a language model touches. Outside it sits every component that decides whether anything actually happens. The separation is the design, not a drawing convention. |
| 2:52 | 17s | slide | Highlight policy, approval, gateway and ledger outside the boundary. | the four services outside | Policy, approval, the action gateway and the audit ledger all sit outside the graph. Every state change has to pass through that one gateway, which checks policy, then approval, then claims an idempotency key before it calls anything external. There is no second path, so there is nothing for a prompt to find. |
| 3:09 | 16s | slide | Zone 0 at the base, struck through and unreachable. | Zone 0 | And at the bottom, the systems a mine actually runs on. Programmable controllers, SCADA, dispatch. They are drawn unreachable because they are unreachable. CAIRN has no control path to operational technology at all. Every artefact it produces is a proposal for a person to act on. |
| 3:25 | 18s | slide | TOGAF ADM view, then the traceability chain | - | TOGAF is what helped us turn these controls into an architecture instead of a collection of prompts. We started with stakeholder concerns, turned them into principles and requirements, mapped those requirements to building blocks, and connected each one to a test. It is a chain of accountability, from the question someone asks to the behaviour the system must prove. |
| 3:43 | 18s | slide | Animate the safety question through each artefact view | each link in turn | Take the safety question on screen. Can CAIRN waive a safety control? The answer becomes a principle: no direct control path to operational technology. That becomes a requirement: high-consequence actions are denied for every role. It becomes a policy service in the architecture, and a test that fails if a model is ever consulted. |
| 4:01 | 11s | slide | Requirements table, test-id column | test-id column | That discipline even caught an inconsistency in our own synthetic scenario. The shift target did not line up with the fleet capacity we had declared. We corrected it before it became a misleading demo. |

## Close - the audit trail, then the thesis

| Cue | Hold | Source | Screen | Highlight | Narration |
|---|---|---|---|---|---|
| 4:12 | 9s | app | Open the audit trace. Scroll the chain: event, evidence, findings, policy, approval, action, outcome. | `.audit` | Every behaviour you have seen here is covered by tests. CAIRN does not replace fleet management, plant control, or the systems a mine already trusts. |
| 4:21 | 9s | app | Close the drawer. The room, reset and quiet, trucks running. | - | It connects them when a decision crosses boundaries, keeps authority with people, and leaves a record of what happened. It recommends. It does not authorise. |

## Recording it

Speak as someone showing a capable product to another professional, not as someone
defending a thesis. Let the screen change before explaining it. Pause after the interlock
denial and after "It recommends. It does not authorise."

The synthesised floor needs no network and no key:

    python3 captures/narrate.py

It takes the words and the timings from this file, speaks each line with macOS `say`, lays
it at its cue, and reports any line that overruns.

## What must not be said

- Do not claim CAIRN replaces fleet management, plant control, ERP, CMMS, or a
  MineRP-class platform.
- Do not imply the figures come from a real operation. The script says they are synthetic
  in its second line. Keep that line.
- Do not describe the fixture provider as a language model. If a Bedrock run is shown,
  name the model that ran.
- Do not say "fully autonomous". The entire point is that it is not.