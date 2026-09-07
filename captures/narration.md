# Narration cue sheet

Runtime **4:48** against a 5:00 cap.

## Why it is structured this way

The left-hand column of the UI is the decision loop, and it is on screen from the first
frame. It lists eight stages. Five are where a language model does the thinking. Three
carry the words `no model`, because the model is not permitted near them.

That split is the product's entire argument, drawn in the interface before anyone says a
word. So the script introduces the column early and then walks it in order: the five
model stages, then the three that refuse. Every later beat has a place in that structure
instead of being another feature in a list.

An earlier version of this sheet opened with seventy-eight words of scene-setting, named
the product at 0:26, mentioned Strands once in passing, and delivered TOGAF as
`PR-05 → AR-05 → SBB-04` in the last twenty seconds. It answered none of the four
questions a judge actually has: what is this for, what is the edge, why Strands, and what
did TOGAF change.

## How to read the table

`Screen` is what the capture must show. `Highlight` names the element a capture-only
overlay must ring, dimming the rest of the page - the video has to point at the thing
being talked about, not hope the viewer finds it.

Word budgets assume 2.5 words per second, a measured control-room pace. If a line runs
long, cut the sentence rather than talking faster; `narrate.py` reports every overrun
against its beat.

## Act 1 - what it is, and the edge

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 0:00 | 16s | Normal shift, trucks running their routes | — | This is CAIRN, a decision fabric for an open-pit iron ore mine. Its job is to take several things going wrong at once, work out that they are one problem, and put costed recovery options in front of a supervisor. |
| 0:16 | 14s | Slow drift across the pit | — | This is the shift it is built for. Eight hours into twelve. The crusher is down to seventy-five per cent. A haul truck has stopped. Rain closes the main ramp in forty-two minutes. |
| 0:30 | 10s | Timeline strip, four source systems | `#timeline` | Four separate systems each know one of those facts. Not one of them knows they are the same problem. That gap is the product. |
| 0:40 | 16s | The decision loop at rest | `.spine` | Before anything happens, look at the left-hand column. That is the decision loop, and it is the whole design in one glance. Five stages where a model thinks. Three that say `no model`, because it is not allowed near them. |

## Act 2 - the five model stages, and why Strands

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 0:56 | 10s | Inject all, then Run analysis | `#timeline` | Five signals arrive from four source systems. CAIRN correlates them into a single incident with a forty-two minute decision window. |
| 1:06 | 18s | Specialists complete, spine fills | `.spine` | The thinking runs as a Strands graph. Four specialists execute in parallel - operations, reliability, risk and options - and you are watching that graph fill as each one finishes. Strands earns its place for two reasons, and both are on screen. |
| 1:24 | 16s | Push in on the per-node timings | `.spine .lvl u` | First, it bounds the work. A fixed node budget, a hard per-node timeout, and no path that can loop forever. Every stage reports the milliseconds it actually took, so the cost of a decision is measured rather than estimated. |
| 1:40 | 20s | Agent cards, tool chips, evidence counts | `#agentList` | Second, the edges carry typed results, not text. The risk specialist's finding reaches the planner as structured data with evidence ids attached. That is testable: remove a hazard and the plan changes. An evaluation case proves it, because an earlier version of this graph looked right and was not reading its edges at all. |

## Act 3 - the three stages that refuse

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 2:00 | 12s | STALE and CONFLICT flags | `#evidenceList` | It does not tidy up bad inputs either. Truck 204's telemetry is fifteen minutes stale, and is marked stale. Two weather sources disagree by thirteen minutes, and both are kept. |
| 2:12 | 12s | Three cards, land on Recover tonnes | `#scenarioCards` | Three options, trading different things away. Recover tonnes returns the most. All three respect the ramp closure, because that is a standing geotechnical control no option may trade. |
| 2:24 | 24s | Attempt interlock override, hold the toast | `#toast` + `Policy` row | Now the first stage that refuses. Policy. Watch what happens when it is asked to do something it must never do. Denied. Rule T4-prohibited-interlock, tier four, decided by a deterministic policy table with no model call at all. No prompt gets past this, because the model is not in the path. A test fails the build if one is ever consulted. |
| 2:48 | 14s | Request approval, then approve | `#toast` | The second is Act, and nothing reaches it without a person. Policy escalates to a named role. The supervisor approves, and the token is scoped to those assets, bound to that plan version, expiring, single-use. |
| 3:02 | 10s | Simulate dispatch timeout | `#toast` | Then the world misbehaves. Dispatch times out after the call may already have applied. |
| 3:12 | 8s | Blind retry refused | `#toast` | A retry is refused. CAIRN cannot prove the first call did not land, so it will not send a second. |
| 3:20 | 10s | Reconcile outcome | `Verify` row | The third is Verify. Only an authoritative confirmation closes it. Unknown, then reconciling, then succeeded. |

## Act 4 - what TOGAF actually changed

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 3:30 | 14s | ADM phase wheel, phases A to H | — | CAIRN was designed as a TOGAF ADM cycle, and the reason that matters is traceability. Every requirement can be followed from the person who raised it to the test that proves it. |
| 3:44 | 30s | Animate the chain, one link per clause | each link in turn | Take one question. A safety authority asks whether this system can waive a safety control. In the stakeholder matrix that becomes a recorded concern. In the principles it becomes: no direct control path to operational technology. In the requirements it becomes: deny every tier four action, for every role. In the architecture it becomes a single building block, the policy service. And it lands in one file, with one test that fails the build if a model is ever consulted. |
| 4:14 | 16s | Requirements table, test-id column | test-id column | One question, five artefacts, one test, and that chain exists for all fifteen requirements. The method also earned its keep. The compliance review is where I found a shift target a quarter of what that fleet actually moves. |

## Close

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 4:30 | 18s | The room, reset and quiet | — | A hundred and ten tests. Thirteen of thirteen evaluation cases. Zero prohibited actions allowed, zero approvals bypassed. Every other system knows its own domain. CAIRN connects them, argues the trade-offs, gets a person to sign, and leaves a record of the whole decision. It recommends. It does not authorise. |

## Recording it

A human voice is worth more than a clean one. Record in one pass against the cut; retakes
per beat are cheap, because the beats are fixed and the fixture replays identically.

The synthesised floor, which needs no network and no key:

    python3 captures/narrate.py

It reads the words from this file and the timings from `captures/beats.json`, speaks each
line with macOS `say`, lays it at its beat, and reports any line that overruns.

## What must not be said

- Do not claim CAIRN replaces fleet management, plant control, ERP, CMMS, or a
  MineRP-class platform.
- Do not imply the figures come from a real operation. Say once, early, that they are
  synthetic.
- Do not describe the fixture provider as a language model. If a Bedrock run is shown,
  name the model that ran.
- Do not say "fully autonomous". The entire point is that it is not.
