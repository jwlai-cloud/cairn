# 8. Visual Demo Plan

## 8.1 Purpose

The demo should make CAIRN feel like an operational decision room, not a chatbot and not a decorative digital-twin tour.

The visual layer is a synthetic, read-only mine view. It shows where the disruption is happening, how the affected systems are connected, what the agents know, which recovery options are feasible, and what an accountable person approved.

## 8.2 Current implementation boundary

The repository currently contains the architecture pack and Claude Code handoff. It does not yet contain an implemented frontend or 3D scene.

The first visual slice should therefore use a deterministic synthetic mine model. It must not require GIS data, photorealistic terrain, live telemetry, or mine-system credentials.

## 8.3 Recommended visual approach

Build a stylised 3D operational twin rather than attempting to reproduce MineTwin's photorealistic experience.

### Recommended stack

- **Frontend:** small React/Vite application, or the simplest frontend already selected by the implementation agent.
- **Scene:** Three.js for a controlled, deterministic open-pit scene.
- **Fallback:** a 2D/isometric view using the same asset and event data if WebGL fails.
- **Data:** synthetic `siteModel`, `operationalEvents`, `agentRuns`, `scenarioOptions`, `approval`, and `outcome` objects.
- **Visual contract:** the frontend consumes CAIRN API/read-model data; it does not contain policy logic.

Cesium can remain the enterprise target for geographic terrain and mine-scale spatial data. For the hackathon, Three.js is the faster route to a reliable scene that can be reset and replayed during a live demo.

## 8.4 Situation-room layout

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ CAIRN  | SHIFT 14:00 | SITE: NORTH PIT | INCIDENT: RECOVERY IN PROGRESS │
├───────────────────────────────┬─────────────────────────────────────────┤
│                               │ Incident brief                          │
│        3D mine scene          │ Crusher derate + truck offline          │
│                               │ Weather window: 42 minutes             │
│   pit benches / roads         │ Confidence: 0.86                        │
│   crusher / stockpile         │                                         │
│   trucks / weather cell       │ Agent activity                          │
│   red/yellow event overlays   │ ✓ Situation     ✓ Reliability            │
│                               │ ✓ Operations    ✓ Risk and HSE            │
│                               │ → Scenario planner                       │
├───────────────────────────────┴─────────────────────────────────────────┤
│ Option A: protect safety | Option B: recover tonnes | Option C: preserve  │
│ equipment       [evidence] [constraints] [impact] [approval required]   │
├─────────────────────────────────────────────────────────────────────────┤
│ Event timeline  14:03 ─ 14:08 ─ 14:12 ─ 14:17   [Approve] [Audit trace] │
└─────────────────────────────────────────────────────────────────────────┘
```

### Scene elements

- Open-pit benches and haul roads.
- Crusher, plant, stockpile, workshop, and weather cell.
- Six to ten haul trucks with simple animated movement.
- Asset status colours: green normal, amber constrained, red failed, blue selected.
- Pulsing event markers with a short label and timestamp.
- Animated route overlays for each proposed recovery scenario.
- A visible "data stale" badge when a source fixture is deliberately delayed.

The scene should be legible within two seconds. Avoid dense labels, realistic textures, and unnecessary camera movement.

## 8.5 Three-minute demo narrative

### 0:00–0:25 — Normal shift

Show the mine running normally. The KPI strip displays tonnes moved, crusher availability, active trucks, weather window, and unresolved risks. Select the crusher to show its linked operational facts.

### 0:25–0:50 — Compound disruption

Inject three or four deterministic events:

1. Crusher throughput drops by 25%.
2. One haul truck becomes unavailable.
3. Rain is forecast to close a route within 42 minutes.
4. The maintenance crew is already committed elsewhere.

The 3D scene highlights the affected assets and the system groups them into one incident rather than four unrelated alerts.

### 0:50–1:20 — Agent collaboration

Show the bounded workflow running in parallel:

- Situation agent builds the current-state summary.
- Reliability agent identifies maintenance constraints.
- Operations agent generates feasible dispatch alternatives.
- Risk and HSE agent identifies the weather and route-control issue.

Each result should show evidence IDs, assumptions, confidence, and completion status. Do not show raw chain-of-thought.

### 1:20–1:55 — Scenario comparison

Present three options on the bottom rail:

- **Protect safety:** close the exposed route and accept lower tonnes.
- **Recover tonnes:** reroute trucks and use the stockpile buffer.
- **Preserve equipment:** reduce crusher feed and prioritise maintenance.

Each card shows expected tonnes, recovery time, safety risk, operational constraints, and required approval.

Selecting an option animates its route and asset impact in the 3D scene.

### 1:55–2:15 — Policy denial

Attempt a deliberately prohibited action, such as changing a safety interlock or approving a permit outside the user's role. The policy service rejects it independently of the model.

This is the most important enterprise credibility moment: the model can recommend, but it cannot authorise.

### 2:15–2:40 — Human approval and simulated action

The shift boss approves the selected recovery plan. CAIRN creates a simulation-only work order and shift instruction with an approval token and idempotency key.

The scene updates the affected truck routes and marks the plan as "approved — execution simulated."

### 2:40–3:00 — Outcome and audit

Inject the outcome event. Show whether the crusher recovered, whether tonnes improved, and whether any risk remains open. Open the audit drawer to trace:

```text
source event → evidence → agent findings → scenario → policy decision
→ human approval → action request → outcome
```

## 8.6 What makes this different from a digital-twin demo

The 3D scene is not the product. It is the spatial interface for the decision loop.

The judging message should be:

> Existing systems know what happened in their own domain. CAIRN connects the domains, explains the trade-offs, obtains accountable approval, and closes the loop.

Do not claim that CAIRN replaces fleet management, plant control, ERP, CMMS, or MineRP-style platforms. Show it integrating their read models and returning approved artefacts through controlled adapters.

## 8.7 Implementation order for Claude Code

1. Create a deterministic `siteModel.json` with pits, routes, assets, and coordinates.
2. Render the static 3D scene and a 2D fallback.
3. Add the event replay control and asset highlighting.
4. Add the incident, agent-status, and evidence panels.
5. Add scenario cards and route overlays.
6. Add policy denial, approval, simulated action, and audit states.
7. Add one reset button so the entire demo can be replayed reliably.
8. Capture screenshots at normal shift, disruption, scenario comparison, policy denial, and audit states.

If time is short, prioritise event highlighting, scenario comparison, approval, and audit over terrain detail.

## 8.8 Definition of done

- A clean checkout starts the visual demo with documented commands.
- The same fixture replay produces the same visible incident and options.
- The mine scene clearly identifies the affected asset and route.
- At least three recovery options show explicit trade-offs.
- A prohibited action is visibly denied by non-LLM policy logic.
- Approval is required before the simulated side effect.
- The audit view reconstructs the complete decision chain.
- The 2D fallback remains usable if 3D rendering fails.
- No live mine data, credentials, or OT control path is required.
