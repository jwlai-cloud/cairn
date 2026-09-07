# 1. Architecture Vision

## 1.1 Purpose

This document defines the architecture vision for CAIRN, an enterprise agent platform for mining operations. It is the Phase A anchor for a TOGAF-style architecture effort: it establishes the business problem, stakeholders, target outcomes, principles, scope, and the first implementation slice.

## 1.2 Problem statement

Mining operations are managed through many specialised systems and handovers. A disruption in one area can cascade through fleet availability, processing capacity, maintenance, safety controls, weather exposure, inventory, and customer commitments. The information exists, but the decision path is fragmented and difficult to reconstruct.

### How might we

> How might we help a mine shift team detect compound operational risk, compare recovery options, and coordinate an approved response across operational silos—without allowing an AI system to bypass accountable human decisions or safety controls?

## 1.3 Product thesis

CAIRN is not a conversational interface over documents. It is an operational decision fabric with:

- A canonical event model for assets, locations, conditions, risks, decisions, actions, and evidence.
- A bounded workflow of specialist agents that reason over the same operational context.
- Deterministic policy and approval gates outside the model.
- Tool calls that can read operational state and create approved work artefacts.
- Evidence, provenance, and outcome tracking for every recommendation.

## 1.4 Stakeholders and users

| Stakeholder | Decision need | CAIRN value |
|---|---|---|
| General manager / operations leader | Understand production risk and recovery trade-offs | A concise, evidence-backed situation view and decision record |
| Shift boss / control-room lead | Stabilise the current shift | Prioritised actions, dependencies, and handover continuity |
| Maintenance planner | Re-sequence constrained work | Impact-aware work packages and collision detection |
| Processing superintendent | Protect plant throughput and quality | Scenario comparisons tied to equipment and feed constraints |
| Geotechnical / HSE lead | Keep people and operations within controls | Risk evidence, required checks, and approval gates |
| Dispatch / fleet coordinator | Rebalance mobile assets and routes | Constraint-aware fleet and haulage options |
| Technology / enterprise architect | Scale the capability across sites | Reusable contracts, governance, and integration boundaries |
| Auditor / regulator / community liaison | Reconstruct why a decision was made | Immutable evidence and accountable decision history |

## 1.5 Business capabilities

### Target capabilities

1. Operational situation awareness
2. Compound-risk detection
3. Cross-functional scenario planning
4. Accountable decision approval
5. Work-package and communication coordination
6. Shift handover continuity
7. Action verification and learning
8. Evidence and governance reporting

### Initial capability slice

**Shift recovery planning** is the first slice. It is narrow enough for a hackathon but demonstrates the full enterprise pattern:

```text
Observe → Correlate → Assess → Generate options → Review policy
        → Obtain approval → Coordinate actions → Verify outcome
```

## 1.6 Initial business scenario

At 10:15, a primary crusher derates to 55% capacity. At 10:19, a haul truck becomes unavailable. A weather service reports heavy rainfall in two hours, while a planned maintenance crew is already committed to a pump job.

CAIRN must:

1. Correlate the events by site, time window, asset dependencies, and operational context.
2. Explain the likely cascading impacts without inventing missing facts.
3. Ask specialist agents to produce constrained recovery options.
4. Compare options by safety, throughput, schedule, maintenance, energy, and confidence.
5. Identify decisions that require the shift supervisor, maintenance planner, or HSE lead.
6. Produce a proposed shift plan and action list.
7. Obtain approval before creating state-changing records.
8. Record the decision, evidence, approver, actions, and measured outcome.

## 1.7 Objectives and measurable outcomes

| Objective | Prototype measure | Longer-term enterprise measure |
|---|---|---|
| Improve response speed | Time from event injection to ranked plans | Time from detection to approved recovery plan |
| Preserve decision quality | Scenario completeness and constraint coverage | Recovery plan acceptance and post-shift variance |
| Reduce coordination loss | Number of handoff artefacts generated | Fewer duplicated or conflicting work requests |
| Improve auditability | Evidence coverage for each recommendation | Reconstructable decision chain for each high-impact action |
| Protect safety boundaries | Zero prohibited autonomous actions in tests | Zero policy bypasses in controlled deployment |

## 1.8 Architecture principles

1. **Safety and accountability precede autonomy.** The system may recommend and coordinate; designated people remain accountable for consequential decisions.
2. **Evidence before confidence.** Every material claim links to source events, timestamps, or documents. Unknown information is represented as unknown.
3. **Bounded autonomy.** Agents operate within explicit scopes, budgets, timeouts, tool allow-lists, and approval tiers.
4. **Deterministic control around probabilistic reasoning.** Business rules, authorization, validation, idempotency, and side-effect controls are implemented outside the model.
5. **One operational vocabulary.** Agents share typed canonical objects rather than passing informal prose as the system of record.
6. **Design for replay.** A scenario can be rerun from a fixed event set, model configuration, policy version, and tool responses.
7. **Integrate at the boundary.** External systems are adapters; domain agents do not contain vendor-specific API logic.
8. **Start with a vertical slice.** Prove the complete decision loop before adding more specialist agents or more data sources.

## 1.9 Scope boundary

### In scope

- Synthetic operational events for a mine shift.
- Read-only retrieval from operational data adapters.
- Scenario generation and comparison.
- Policy checks and approval requests.
- Draft work orders, shift instructions, notifications, and reports.
- Evidence and audit trail.
- Local execution and optional deployment to AWS/AgentCore.

### Out of scope

- Autonomous actuation of operational technology.
- Safety-critical alarm suppression or interlock control.
- Unreviewed external communication about an emergency.
- Automated regulatory certification or compliance attestation.
- Training a new foundation model.

## 1.10 TOGAF alignment

| TOGAF concern | CAIRN artefact |
|---|---|
| Architecture Vision | This document and the demo scenario |
| Business Architecture | Capability map, stakeholders, value stream, decision rights |
| Data Architecture | Mine event graph, evidence model, canonical contracts |
| Application Architecture | Supervisor, specialist agents, tools, policy, approval, audit services |
| Technology Architecture | Runtime, model provider, eventing, storage, identity, observability |
| Opportunities and Solutions | Phased vertical slice and reusable building blocks |
| Migration Planning | Compressed delivery roadmap and site-by-site expansion plan |
| Implementation Governance | Acceptance criteria, safety gates, test evidence, change control |
| Architecture Change Management | ADRs, versioned contracts, model/policy change review |
