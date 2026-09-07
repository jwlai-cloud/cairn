# 10. Demo Video: Method and Script

**Runtime target:** 4:30 against a 5:00 hard cap
**Thesis:** *Existing systems each know one domain. CAIRN connects them, and then refuses to act on its own.*

The rules score Presentation on whether the video "clearly demonstrates the project working end-to-end" and whether the pitch communicates problem, audience, and why it matters. Everything below is built to satisfy that, and to spend the extra ninety seconds on the two things a Professional Agents judge actually cares about: **can this thing hurt anyone, and does it fall over.**

## 10.1 What the video has to prove

Ranked by how much it moves the score, not by how interesting it is to build.

| # | Claim | Shown by | Why it matters |
|---|---|---|---|
| 1 | The model cannot authorise anything | Tier 4 denial with rule id, tier, and `decidedBy: deterministic policy service (no model call)` | The single most credible enterprise moment available |
| 2 | A state change needs an accountable human | Policy escalates, named role approves, token bound to plan version and evidence hash | Separates this from a chatbot with tools |
| 3 | It fails safe when the world is ambiguous | Dispatch timeout → `UNKNOWN`, blind retry refused, explicit reconciliation | Reliability, and almost nobody else will show it |
| 4 | It does not smooth over bad data | Stale evidence flagged, two conflicting forecasts both retained | Honesty as a feature |
| 5 | The reasoning is inspectable, not a black box | Bounded graph, per-node tools and measured durations, no chain-of-thought | Technical implementation |
| 6 | Every claim traces to a passing test | TOGAF requirement → test id, on screen | Turns process into evidence |
| 7 | It correlates rather than alerts | Five signals from four systems become one incident | The actual product idea |

## 10.2 Method

**Capture.** `node captures/capture.mjs` drives the real application through the real API. Nothing is mocked for the camera, and no frame is a slide pretending to be software.

**Resolution.** Record a 1920×1200 viewport with the page zoomed 1.5×, then export at 4K.

Two independent things get confused here. **Viewport width sets apparent size**: a layout that computes at an effective 1280 CSS width and paints into 1920 real pixels is 1.5× larger in frame than the same layout at 1920. **Export resolution sets sharpness**, and only that. Recording 4K at a 1920 viewport gives sharp, tiny text; that is the trap. Playwright's `recordVideo.size` pads rather than scales, so asking for a canvas larger than the viewport letterboxes the page into a corner — the zoom is what does the work.

**Timing.** `capture.mjs` measures where each beat actually lands in the recording and writes `captures/beats.json`; `edit.sh` and `captions.py` read only that. Nothing downstream is hand-timed, because the requested hold and the recorded position are not the same number — every click carries Playwright's actionability checks and every `evaluate` a round trip, and on a page running a 3D scene that added twenty-nine seconds across a four-minute take, unevenly spread. Timings cut to the requested holds put the denial caption twenty-four seconds past its own toast.

**Narration and speed are mutually exclusive.** The raw take already fits the cap, so no beat is compressed. A beat sped up 2× has half the room for words, and the cue sheet in `captures/narration.md` is written to the recorded durations. Speed is worth reintroducing for exactly one thing — a live model inference with nothing being said over it — and it should arrive then, per beat, not as a standing setting.

**Captions.** Burned in from the same beat file, stating what each beat *proves* rather than describing the screen. They are not a substitute for narration; they are what carries the argument for a judge watching muted or at 360p on a phone. Rendered after the 4K upscale so the type is drawn at output resolution rather than scaled up into it.

**Determinism.** The fixture replays identically, so a retake is frame-comparable to the take before it. If a beat lands badly, re-shoot only that beat.

**Motion.** The application already animates: haul trucks crawl their routes, status beacons pulse and bloom, route overlays light when a plan is selected, the decision spine fills as nodes complete. Add only two post effects, both in service of reading:

- a slow push-in on the denial toast and on the audit chain, so small type is legible at 1080p;
- a one-second hold before each click, so a viewer sees the state *before* it changes.

No transitions, no music stings, no kinetic type. The subject is a control room; restraint is the aesthetic.

## 10.3 Script

Times are cumulative. Narration is what gets said; Screen is what the capture must show.

---

### 0:00 – 0:30 · The problem

> **Narration.** Eight hours into a twelve-hour shift at an open-pit iron ore mine. Four different systems are each about to be completely right, and useless. Plant control knows the crusher is down to seventy-five per cent. Fleet management knows a haul truck just stopped. The weather service knows rain closes the main ramp in forty-two minutes. The maintenance system knows the only crew is committed elsewhere until ten past four.
>
> Not one of them knows those are the same problem. The shift supervisor works that out under time pressure, from four screens, while the window closes.

**Screen.** Normal shift. KPI strip: 16,900 t of a 28,000 t target, crusher 100%, eight trucks, no alerts. Slow drift over the pit; trucks running their routes.

---

### 0:30 – 1:00 · Correlation

> **Narration.** CAIRN takes those four feeds and does the thing none of them can: it says they are one incident, not five alerts. Five signals, four source systems, one compound disruption with a forty-two minute decision window.

**Screen.** Click **Inject all** — timeline fills, assets go amber and red, rain cell appears. Click **Run analysis**. Four specialists run in parallel, the spine fills left to right with real millisecond timings, the incident brief writes itself.

---

### 1:00 – 1:30 · Evidence, including the bad kind

> **Narration.** Every claim carries an evidence id. And where the evidence is bad, it says so rather than smoothing it over. Truck 204's telemetry is fifteen minutes stale — flagged, not quietly used. Two weather sources disagree by thirteen minutes — both kept, neither silently discarded, and the plan uses the earlier arrival because that is the conservative one.

**Screen.** Push in on the STALE and CONFLICT flags. Then the agent cards: tool chips, evidence counts, confidence, measured durations.

---

### 1:30 – 2:00 · Three options that actually differ

> **Narration.** Three recovery options, and they trade different things away. Protect safety: stand down early, four thousand nine hundred tonnes. Recover tonnes: reroute and draw the stockpile, seven thousand six hundred. Preserve equipment: cap the crusher, six thousand one hundred, but the inspection gets done. All three respect the ramp closure, because that is a standing geotechnical control and no option is allowed to trade it away.

**Screen.** Click each card in turn; route overlays and affected assets change in the scene each time. Land on **Recover tonnes**, recommended, with the reason line visible.

---

### 2:00 – 2:40 · The model cannot authorise anything

> **Narration.** Now the part that matters. Watch what happens when the system is asked to do something it must never do.
>
> *(click)*
>
> Denied. Rule T4-PROHIBITED-INTERLOCK, tier four, decided by a deterministic policy service — with no model call at all. Safety interlocks are outside CAIRN's authority. There is no prompt, no jailbreak, and no clever wording that gets past this, because the model is not in the decision path. It is a table lookup, and it is covered by a test that fails the build if a model is ever consulted.

**Screen.** **Attempt interlock override.** Hold on the denial toast; push in until `decidedBy: deterministic policy service (no model call)` fills the frame. Cut briefly to `app/policy/decisions.py` — the `RULES` table and Tier 4 entries.

---

### 2:40 – 3:10 · A human has to sign

> **Narration.** Even a permitted action doesn't just happen. Policy escalates it to a named role. The shift supervisor approves, and the token that comes back is scoped to those assets, bound to that plan version and that evidence set, expires, and is good exactly once. Change the plan and the approval is void.

**Screen.** **Request approval** → **Approve as SHIFT_SUPERVISOR**. Push in on the token, evidence hash and expiry.

---

### 3:10 – 3:50 · When the world is ambiguous, fail safe

> **Narration.** Real systems time out. So: approved plan, dispatch call, and no answer — after the call may already have applied.
>
> A naive agent retries and raises the work order twice. CAIRN holds the outcome in UNKNOWN and refuses to retry, because it cannot prove the first call didn't land. Ask it to try again and it says no. It stays unknown until something authoritative confirms it — then, and only then, UNKNOWN to RECONCILING to SUCCEEDED.

**Screen.** **Simulate dispatch timeout** → UNKNOWN toast. Attempt the retry → `RECONCILIATION_REQUIRED`. Then **Reconcile outcome** → both actions resolve.

---

### 3:50 – 4:10 · Simulation only, and the whole chain

> **Narration.** Every artefact is simulation-only and prefixed SIM. Nothing here touches a mine system, a PLC or a dispatch queue — there is no control path at all, by design. And the entire decision reconstructs: source event, evidence, agent findings, scenario, policy decision, human approval, action, outcome.

**Screen.** Execute action, verify outcome — note truck still down and residual risks still open. Open **Audit trace**, scroll the chain slowly.

---

### 4:10 – 4:40 · Method, and why it is not decoration

> **Narration.** This was built as a TOGAF ADM cycle, not a demo with an architecture diagram bolted on afterwards. One narrow pass: one capability, one increment, one architecture contract.
>
> Here is what that actually means. An HSE authority asks one question — *can this thing waive a safety control?* In the Phase A stakeholder matrix that becomes a recorded concern. In the Preliminary phase it becomes principle PR-05: no direct control path to operational technology. In the requirements specification it becomes AR-05: deny every tier four action, for every role. In Phase E it becomes solution building block SBB-04, the deterministic policy service. And it lands in one file, `app/policy/decisions.py`, with a test that fails the build if a model is ever consulted.
>
> One question, five artefacts, one test. That chain exists for every requirement — fifteen of them, each with the test id that proves it in the compliance table.
>
> And the method paid for itself. Phase G compliance review is where I found a shift target that was a quarter of what that fleet actually moves. Requirements traceability is where I found a decision rail decorated with invented survey elevations, in a system whose entire claim is that it does not invent numbers. An evaluation case is where I found an agent graph whose nodes were not reading each other at all.
>
> None of those were caught by tests I wrote to pass. They were caught by asking, formally, whether the thing I built matched the thing I said I was building.

**Screen.** Animate the chain as it is spoken, one element at a time, on a single still frame:

```
  HSE authority  ──▶  PR-05  ──▶  AR-05  ──▶  SBB-04  ──▶  decisions.py  ──▶  ✓ test
  "can it waive       no OT      deny tier 4   deterministic   RULES table    tier-4-denied
   a control?"        control    every role    policy                        -for-every-role
```

Then cut to the `09 §9.12` requirements table with the test-id column highlighted, and a green CI run beside it.

---

### 4:40 – 5:00 · Close

> **Narration.** A hundred and seven tests. Thirteen of thirteen evaluation cases. Zero prohibited-action violations, zero approval bypasses, and a replay that matches every time.
>
> Existing systems know what happened in their own domain. CAIRN connects them, argues the trade-offs, gets a person to sign, and leaves a record that reconstructs the whole decision. It recommends. It does not authorise.

**Screen.** End on the room, reset and quiet, trucks running.

---

## 10.4 Cutting order if it runs long

Cut in this order, and stop as soon as it fits:

1. Second and third option cards (1:30) — keep only the recommended one.
2. The evidence push-in (1:00) — the flags are legible in the wide shot.
3. Audit scroll (3:50) — a static frame of the chain carries it.
4. The correlation beat's tail (0:30).

**Never cut:** the denial, the approval token, or the UNKNOWN/reconcile sequence. Those are claims 1, 2 and 3, and they are the reason to prefer this entry over a chatbot with tools.

## 10.5 What must not be said

- Do not claim CAIRN replaces fleet management, plant control, ERP, CMMS, or a MineRP-class platform.
- Do not imply the figures are from a real operation. They are synthetic and internally consistent; say so once, early.
- Do not describe the fixture model as a language model. In the recorded run the graph is real and the model provider is deterministic; if a Bedrock run is shown, say which model.
- Do not say "fully autonomous". The entire point is that it is not.
