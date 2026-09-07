# Narration cue sheet

Runtime **4:48** against a 5:00 cap.

## The arc, and why this one

Story carries emotional truth. Story is not evidence. Use story to make people care, and
use evidence to make them right.

Two earlier drafts had that backwards. They opened on systems rather than people, and
tried to make the audience care by proving correctness at them. Counting the words showed
it plainly. Across 694 spoken words, `supervisor` appeared twice, and `crew`, `operator`
and `someone` never appeared at all. Nobody was in the story, and no line said what the
thing was worth. An outside reviewer called it an engineer defending an implementation.
That was fair.

The shape is now:

| Act | Beat | Job |
|---|---|---|
| 1 | A supervisor, four screens, forty-two minutes | Make someone care |
| 2 | The decision, made visible | Show it working, and say why Strands |
| 3 | The three stages that refuse | Earn trust with evidence |
| 4 | Why it is built this way | Argue the value to a business |
| Close | Numbers, then the thesis | Land the differentiator |

Act 1 is a protagonist arc. Act 4 is the value argument, which no earlier draft had at
all. Evidence still carries Acts 3 and 4, but it now earns trust instead of defending a
design.

The left column of the interface is on screen from the first frame. It lists eight
stages: five where a model thinks, three marked `no model`. That split is the product's
whole claim, already drawn in the interface. Act 1 introduces it, and the rest of the
script walks it in order.

## Craft rules applied

- Replace an em dash with a new sentence. Use periods, not semicolons.
- Say who does what. "Policy escalates it", not "the action is escalated".
- One thought per sentence. Split anything over about 25 words.
- Cut every word that does no work.
- Be specific rather than sterile. "Truck 204's telemetry is fifteen minutes old", not
  "data quality is surfaced".
- Vary sentence length on purpose. A short sentence lands a point. A longer one carries a
  fact together with its condition.
- No idioms and no metaphors. A judge may not be a native speaker.
- Do not manufacture tension. The forty-two minutes is in the fixture. Stakes are real or
  they go unstated.

## How to read the table

`Screen` is what the capture must show. `Highlight` names the element a capture-only
overlay must ring while dimming the rest of the page. The video has to point at whatever
is being discussed.

Budgets assume about 2.5 words per second. `narrate.py` reports any line that overruns
its beat. When one does, cut a sentence rather than speaking faster.

## Act 1 - a supervisor, four screens, forty-two minutes

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 0:00 | 14s | Normal shift, trucks running their routes | - | Eight hours into a twelve-hour shift, a supervisor at an open-pit iron ore mine has four screens and one decision to make. Rain closes the main haul ramp in forty-two minutes. |
| 0:14 | 16s | Slow drift across the pit, KPI strip legible | `#kpiStrip` | Every screen is right. Plant control says the crusher is down to seventy-five per cent. Fleet says a truck has stopped on the ramp. Maintenance says the only crew is committed until ten past four. |
| 0:30 | 14s | Timeline strip, four source systems | `#timeline` | No screen says those are one problem. Working that out is the supervisor's job. CAIRN does it instead, and it is built on a rule most agents break. It recommends. It never authorises. |
| 0:44 | 14s | The decision loop at rest | `.spine` | That rule is drawn in the left column. Eight stages. Five where a model thinks. Three that say `no model`, because a model is not allowed to decide them. |

## Act 2 - the decision, made visible

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 0:58 | 10s | Inject all, then Run analysis | `#timeline` | Five signals arrive from four source systems. CAIRN correlates them into one incident and starts a forty-two minute clock. |
| 1:08 | 18s | Specialists complete, spine fills | `.spine` | The thinking runs as a Strands graph. Four specialists work at once on operations, reliability, risk and options. Strands is here for two reasons, and you can watch both rather than take them on trust. |
| 1:26 | 16s | Push in on the per-node timings | `.spine .lvl u` | First, it bounds the work. A fixed node budget. A hard timeout on every node. No path that can loop forever. Each stage reports the milliseconds it took, so a decision has a measured cost. |
| 1:42 | 22s | Agent cards, tool chips, evidence counts | `#agentList` | Second, the graph carries typed results along its edges instead of pasted text. The risk specialist's finding reaches the planner as structured data with evidence ids attached. Remove a hazard from the input and the plan changes. An evaluation case proves that, because an earlier version of this graph looked right and never read its own edges. |

## Act 3 - the three stages that refuse

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 2:04 | 12s | STALE and CONFLICT flags | `#evidenceList` | It does not tidy up bad inputs. Truck 204's telemetry is fifteen minutes old, and it says so. Two weather sources disagree by thirteen minutes, and it keeps both. |
| 2:16 | 12s | Three cards, land on Recover tonnes | `#scenarioCards` | Three options, each giving up something different. Recover tonnes returns the most. All three keep the ramp closed. That closure is a geotechnical control, and no option may trade it. |
| 2:28 | 24s | Attempt interlock override, hold the toast | `#toast` and `Policy` row | Now the first stage that refuses. Ask CAIRN to override a safety interlock. Denied. Tier four, rule T4 prohibited interlock, decided by a policy table with no model call at all. No prompt gets past this, because no model is in the path. A test fails the build if one ever is. |
| 2:52 | 14s | Request approval, then approve | `#toast` | The second refusing stage is Act. Nothing reaches it without a person. Policy escalates to a named role, the supervisor approves, and the token comes back scoped, expiring and single-use. |
| 3:06 | 10s | Simulate dispatch timeout | `#toast` | Then the world misbehaves. Dispatch times out after the call may already have applied. CAIRN holds the outcome as unknown. |
| 3:16 | 10s | Blind retry refused | `#toast` | Ask it to retry and it refuses. It cannot prove the first call failed, so it will not risk sending a second. |
| 3:26 |  8s | Reconcile outcome | `Verify` row | The third refusing stage is Verify. Only an authoritative confirmation closes an unknown outcome. |

## Act 4 - why it is built this way

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 3:34 | 16s | ADM phase wheel, phases A to H | - | A mine will not wire an agent into its operations because a demo went well. It needs to know that every safety rule has a home and a test. That is why CAIRN was designed as a TOGAF ADM cycle. |
| 3:50 | 26s | Animate the chain, one link per clause | each link in turn | One question runs the whole way through it. A safety authority asks whether this system can waive a safety control. The stakeholder matrix records that as a concern. The principles answer it: no direct control path to operational technology. The requirements answer it: deny every tier four action, for every role. The architecture answers it with one building block, the policy service. And it ends in one file, with one test. |
| 4:16 | 12s | Requirements table, test-id column | test-id column | One question, five artefacts, one test, and the same chain for all fifteen requirements. The review also caught a shift target a quarter of what that fleet really moves. |

## Close

| Cue | Hold | Screen | Highlight | Narration |
|---|---|---|---|---|
| 4:28 | 20s | The room, reset and quiet | - | A hundred and ten tests. Thirteen of thirteen evaluation cases. No prohibited action allowed. No approval bypassed. Other systems each know their own corner. CAIRN reads them together, argues the trade-offs, gets a person to sign, and leaves a record that rebuilds the decision. It recommends. It does not authorise. |

## Recording it

A human voice is worth more than a clean one. Record in one pass against the cut. Retakes
per beat are cheap, because the beats are fixed and the fixture replays identically.

The synthesised floor needs no network and no key:

    python3 captures/narrate.py

It takes the words from this file and the timings from `captures/beats.json`, speaks each
line with macOS `say`, lays it at its beat, and reports any line that overruns.

## What must not be said

- Do not claim CAIRN replaces fleet management, plant control, ERP, CMMS, or a
  MineRP-class platform.
- Do not imply the figures come from a real operation. Say once, early, that they are
  synthetic.
- Do not describe the fixture provider as a language model. If a Bedrock run is shown,
  name the model that ran.
- Do not say "fully autonomous". The entire point is that it is not.
