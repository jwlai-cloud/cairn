# Narration cue sheet

Read against the **raw** capture, which runs 1.0x throughout and totals 4:10 — fifty
seconds under the cap. The prose script in `docs/architecture/10-demo-video-plan.md`
says what the video argues; this says it at the length each beat actually lasts.

Speed ramps and narration are mutually exclusive. A beat compressed 2x has half the
room for words, and doc 10's script was written for real time. Speed is therefore
reserved for beats with nothing to say over them — a live Bedrock inference is the
only real candidate — and every narrated beat stays at 1.0x.

Budgets below assume 2.5 words per second, which is a measured control-room pace, not
a pitch pace. If a line runs long, cut the sentence rather than talking faster: the
captions carry the claim if the voice does not.

| Cue | Hold | Words | Line |
|---|---|---|---|
| 0:00 | 26s | ~65 | Eight hours into a twelve-hour shift at an open-pit iron ore mine. Four systems are each about to be completely right, and useless. Plant control knows the crusher is down to seventy-five per cent. Fleet management knows a haul truck has stopped. The weather service knows rain closes the main ramp in forty-two minutes. Maintenance knows the only crew is committed until ten past four. Not one of them knows those are the same problem. |
| 0:26 | 12s | ~30 | CAIRN does the thing none of them can. Five signals, four source systems — one compound disruption, with a forty-two minute decision window. |
| 0:38 | 18s | ~45 | Four specialists run in parallel inside a bounded Strands graph. Bounded matters: a fixed node budget, a hard timeout, and edges that carry typed findings — so what each specialist concluded actually reaches the planner, instead of just an ordering. |
| 0:56 | 16s | ~40 | Every claim carries an evidence id. Where the evidence is bad, it says so. Truck 204's telemetry is fifteen minutes stale — flagged, not quietly used. Two weather sources disagree by thirteen minutes. Both are kept. |
| 1:12 | 10s | ~25 | The plan uses the earlier arrival, because that is the conservative one. Tool calls, evidence counts, confidence, measured durations — all on the record. |
| 1:22 |  9s | ~22 | Three options, and they trade different things away. Protect safety: stand down early, four thousand nine hundred tonnes. |
| 1:31 |  8s | ~20 | Preserve equipment: cap the crusher, six thousand one hundred, and the inspection still gets done. |
| 1:39 | 11s | ~27 | Recover tonnes: reroute and draw the stockpile, seven thousand six hundred. All three respect the ramp closure — a standing geotechnical control that no option is allowed to trade away. |
| 1:50 | 26s | ~65 | Now the part that matters. Watch what happens when it is asked to do something it must never do. Denied. Rule T4-PROHIBITED-INTERLOCK, tier four, decided by a deterministic policy service — with no model call at all. There is no prompt and no jailbreak that gets past this, because the model is not in the decision path. It is a table lookup, and a test fails the build if a model is ever consulted. |
| 2:16 | 12s | ~30 | Even a permitted action doesn't just happen. Policy escalates it to a named role — accountability with a person's name on it, not a service account. |
| 2:28 | 16s | ~40 | The shift supervisor approves. The token is scoped to those assets, bound to that plan version and that evidence set, it expires, and it is good exactly once. Change the plan and the approval is void. |
| 2:44 | 16s | ~40 | Real systems time out. Approved plan, dispatch call, and no answer — after the call may already have applied. A naive agent retries, and raises the work order twice. |
| 3:00 | 14s | ~35 | CAIRN holds the outcome in UNKNOWN and refuses to retry, because it cannot prove the first call didn't land. Ask it to try again and it says no: reconciliation required. |
| 3:14 | 12s | ~30 | It stays unknown until something authoritative confirms it. Then, and only then — UNKNOWN, to RECONCILING, to SUCCEEDED. |
| 3:26 | 10s | ~25 | Every artefact is simulation-only. Nothing here touches a mine system, a PLC, or a dispatch queue. There is no control path, by design. |
| 3:36 | 14s | ~35 | And the whole decision reconstructs. This was built as a TOGAF ADM cycle, not a demo with an architecture diagram bolted on afterwards. An HSE authority asks one question: can this thing waive a safety control? |
| 3:50 | 10s | ~25 | That becomes principle PR-05, requirement AR-05, building block SBB-04, one file, and one test — for every requirement. |
| 4:00 | 10s | ~25 | A hundred and eight tests. Thirteen of thirteen evaluation cases. It recommends. It does not authorise. |

## Recording it

A human voice is worth more here than a clean one. Judges hear dozens of videos in an
afternoon and a synthesised track reads as a project that ran out of time. Record into
anything, in one pass, watching the cut — retakes per beat are cheap because the beats
are fixed and the fixture replays identically.

If a human take is not going to happen, the local fallback is macOS `say`, which needs
no network and no key:

    say -v 'Lee (Premium)' -r 165 -o narration.aiff -f captures/narration.txt

`Lee` and `Karen` are the en_AU voices, which suit the site. Treat this as the floor,
not the plan.

## Muxing

    ffmpeg -i captures/cairn-demo.mp4 -i narration.wav -c:v copy -c:a aac -b:a 192k \
      -shortest captures/cairn-demo-voiced.mp4
