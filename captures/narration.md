# Narration cue sheet

Runtime **4:48** against a 5:00 cap. Fourteen cues, every one between 2.1 and 2.6 words
per second.

## Where this version came from

The words are an outside revision, adopted close to verbatim. Two earlier drafts of mine
failed the same way twice: they opened on systems rather than people, and they used proof
to try to make the audience care. Proof cannot do that job. Story carries emotional
truth, evidence makes people right, and they are different jobs.

Three faults the revision caught that mattered more than voice:

- **An internal rule identifier was spoken aloud.** No listener can use one, and reading
  it out signals a system talking about itself. Gone.
- **The word "synthetic" appeared only in my own list of things not to say.** It was
  never in the script. It is now in the second line, which is where the rules need it.
- **The shift-target anecdote could be heard as a real mine statistic.** It was an
  inconsistency in our own synthetic fixture, and it now says so. Presenting it any other
  way would invent a fact about a real industry.

Changes made to the revision, and why:

- "handovers" rather than "hand-offs", which is ordinary usage in shift operations.
- Em dashes replaced with commas or colons, and sentences split, per the technical-writing
  standard.
- Its closing line, "when the shift changes, it can show us whether the decision actually
  worked", is left out. Outcome verification exists, but that phrasing implies tracking
  across shifts, which does not. It would be the one overclaim in the script.
- Two of its sections carried two paragraphs each. Those are split into separate cues so
  the audio tool can place each at its own beat.

## How to read the table

`Screen` is what the capture must show. `Highlight` names the element a capture-only
overlay must ring while dimming the rest of the page. The video has to point at whatever
is being discussed.

`narrate.py` reports any line that overruns its beat. When one does, cut a sentence
rather than speaking faster.

## Act 1 - a shift, not a dashboard

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 0:00 | 22s | Normal shift. Trucks move through the pit. CAIRN visible but quiet. | - | This is CAIRN. In a mine shift, the difficult decisions rarely come from one alarm. They happen when several changes arrive together, across different systems, and nobody has time to assemble the whole picture. CAIRN brings those signals together, tests the options, and helps a supervisor recover the shift safely. |
| 0:22 | 21s | Crusher, truck and weather events land. Timeline begins. | `#timeline` | Everything in this demo is synthetic, but the situation is familiar. The crusher is running at seventy-five percent. A haul truck has stopped. Rain will close the main ramp in forty-two minutes. Each source knows one fact. CAIRN sees one operational problem, and a decision window that is already closing. |
| 0:43 | 19s | The decision spine on the left | `.spine` | That is the idea behind the spine on the left. It is the decision loop: understand the situation, work out the choices, check the risks, then decide and verify. You can also see where the AI stops. Agents help interpret evidence. Policy, approval and execution stay deterministic and accountable. |

## Act 2 - why Strands

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 1:02 | 20s | Four signals arrive. Strands graph starts. Specialists run in parallel. | `.spine` | Five signals arrive from four source systems. CAIRN correlates them into one incident and starts a bounded Strands workflow. Operations, reliability, risk and scenario planning work in parallel, so the decision does not wait on handovers. The graph gives the work clear limits and a clear result. |
| 1:22 | 20s | Specialist nodes complete with measured durations | `.spine .lvl u` | We chose Strands because it gives us a practical way to compose these specialists without building an uninspectable swarm. Each one returns a structured finding rather than a paragraph of text. Evidence, assumptions and uncertainty travel with that finding into the next stage. That makes the reasoning testable, and easier to trust. |

## Act 3 - evidence, options, and where the line is

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 1:42 | 16s | Agent cards complete. Stale telemetry and conflicting sources highlighted. | `#evidenceList` | CAIRN also refuses to make messy data look clean. This truck signal is fifteen minutes old, so it is marked stale. The weather sources disagree, so both readings stay visible. It can reason, but it cannot turn uncertainty into fact. |
| 1:58 | 19s | Three scenario cards. Select the recommended plan, animate its route. | `#scenarioCards` | Here are the recovery choices. One protects safety and accepts lower production. One recovers more tonnes using the stockpile buffer. The third protects the crusher and gives maintenance room to work. The point is not a clever answer. It is a visible trade-off with evidence behind it. |
| 2:17 | 24s | Attempt the interlock override. Hold the denial. Pause. | `#toast` | Now we reach the boundary between intelligence and authority. I will ask for an interlock override. The request is denied by a deterministic policy service before it can become an action. The model may explain a situation or suggest a plan. It does not get to waive a safety control. |
| 2:41 | 19s | Approval request. Named role, plan version, scoped assets. Approve. | `#toast` | For an allowed recovery plan, the system still asks for a person. The approval is tied to the named role, the selected assets and this exact plan version. It expires, it can be used once, and it leaves a record. |
| 3:00 | 24s | Simulate dispatch timeout. Unknown state, then reconciliation. | `#toast` | Then the outside world behaves the way it sometimes does. Dispatch times out after the call may already have applied. CAIRN does not blindly try again. It marks the result unknown and reconciles it against authoritative state. Only when the outcome is confirmed does the work close. Avoiding a duplicate action can matter as much as the original recommendation. |

## Act 4 - what TOGAF changed

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 3:24 | 24s | TOGAF ADM view, then the traceability chain | - | TOGAF is what helped us turn these controls into an architecture instead of a collection of prompts. We started with stakeholder concerns, turned them into principles and requirements, mapped those requirements to building blocks, and connected each one to a test. It is a chain of accountability, from the question someone asks to the behaviour the system must prove. |
| 3:48 | 25s | Animate the safety question through each artefact view | each link in turn | Take the safety question on screen. Can CAIRN waive a safety control? The answer becomes a principle: no direct control path to operational technology. That becomes a requirement: high-consequence actions are denied for every role. It becomes a policy service in the architecture, and a test that fails if a model is ever consulted. |
| 4:13 | 14s | Requirements table, test-id column | test-id column | That discipline even caught an inconsistency in our own synthetic scenario. The shift target did not line up with the fleet capacity we had declared. We corrected it before it became a misleading demo. |

## Close

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 4:27 | 21s | Reset to the situation room. Audit trail, then the quiet mine view. | - | Every behaviour you have seen here is covered by tests. CAIRN does not replace fleet management, plant control, or the systems a mine already trusts. It connects them when a decision crosses boundaries, keeps authority with people, and leaves a record of what happened. It recommends. It does not authorise. |

## Recording it

Speak as someone showing a capable product to another professional, not as someone
defending a thesis. Let the screen change before explaining it.

Pause after the interlock denial, and after "It recommends. It does not authorise." Those
are the two lines the audience should carry out of the video.

Keep "Strands", "TOGAF", "deterministic policy" and "structured finding", and explain each
in ordinary language immediately. Never read component names, rule identifiers, test ids
or internal labels aloud.

A human voice is worth more than a clean one. Record in one pass against the cut. Retakes
per beat are cheap, because the beats are fixed and the fixture replays identically.

The synthesised floor needs no network and no key:

    python3 captures/narrate.py

It takes the words from this file and the timings from `captures/beats.json`, speaks each
line with macOS `say`, lays it at its beat, and reports any line that overruns.

## What must not be said

- Do not claim CAIRN replaces fleet management, plant control, ERP, CMMS, or a
  MineRP-class platform.
- Do not imply the figures come from a real operation. The script says they are synthetic
  in its second line. Keep that line.
- Do not describe the fixture provider as a language model. If a Bedrock run is shown,
  name the model that ran.
- Do not say "fully autonomous". The entire point is that it is not.
