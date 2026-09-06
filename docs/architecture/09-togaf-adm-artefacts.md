# 9. TOGAF ADM Traceability and Artefact Register

**Status:** v0.1 · **Date:** 2026-09-06 · **Architect of record:** CAIRN enterprise architecture
**Scope of this cycle:** one ADM iteration over a single capability — compound-disruption recovery for an open-pit mine shift.

## 9.1 Why a hackathon project runs the ADM at all

The ADM is scaled to the engagement, not skipped. A hackathon iteration is a deliberately narrow ADM cycle: one capability, one increment, one Architecture Definition, one Implementation Governance gate. The value of running it here is not ceremony — it is that every claim in the demo is traceable to a stated requirement, a stated principle, and a governance control that can be tested.

What is deliberately compressed in this cycle:

- One Architecture Definition Document, not separate B/C/D volumes (this pack is the ADD).
- Stakeholder analysis captured as a concerns matrix rather than interview records.
- Capability-based planning limited to one capability increment.
- Architecture Contract is between the architecture pack and the implementation agent, not a supplier contract.

## 9.2 Preliminary Phase — principles and governance

### Architecture principles (Principles Catalog)

| ID | Principle | Rationale | Implication | Verified by |
|---|---|---|---|---|
| PR-01 | The model is not the authorisation boundary | A language model can be induced to agree to anything; accountability cannot rest on it | Policy, approval and identity sit outside the model as deterministic services | `tests/safety/test_policy_denial.py::test_policy_denial_does_not_touch_the_agent_layer` |
| PR-02 | Fail closed | In a high-consequence environment, an unavailable control must block, not permit | Unknown action types, absent approvals and stale-only evidence all deny | `test_action_missing_from_the_policy_table_fails_closed` |
| PR-03 | Evidence before assertion | An operational claim without provenance is not decision-grade | Every agent output carries `evidenceIds`, `assumptions`, `unknowns`, `confidence` | `tests/contract/test_contracts.py::test_every_scenario_exposes_the_required_decision_fields` |
| PR-04 | Separate read, propose and commit | A read-only specialist must not reach a write tool by rewording a prompt | Three tool modules with distinct interfaces; only the gateway commits | `app/tools/` module split |
| PR-05 | No direct control path to operational technology | Zone 0 requires certified control processes CAIRN does not have | Tier 4 actions are enumerated and always denied | `tests/safety/test_policy_denial.py::test_tier_four_is_denied_for_every_role` |
| PR-06 | Reproducibility is a control, not a convenience | An operational decision that cannot be replayed cannot be audited or assured | Fixed fixtures, fixed IDs, deterministic model provider, replay signature | `tests/evaluation/test_replay.py` |
| PR-07 | Contract-first interoperability | Callers must not depend on prompt wording or vendor object shapes | Typed Pydantic contracts, camelCase wire format, versioned schema | `tests/contract/test_contracts.py::test_run_view_serialises_as_camel_case` |
| PR-08 | Uncertainty is reported, not resolved away | Silently picking one of two conflicting sources destroys the audit trail | Conflicts and staleness are surfaced in the read model and the UI | `tests/safety/test_evidence.py` |

### Governance framework for this cycle

| Control | Mechanism | Location |
|---|---|---|
| Architecture compliance review | Definition-of-done checklist per document | `06 §6.6`, `08 §8.8` |
| Change control | ADRs, superseded not edited | `docs/architecture/decisions/` |
| Release gate | Contract + safety + evaluation suites must pass | `06 §6.8`, `tests/` |
| Source-branch protection | `main` accepts merges through pull request only | GitHub branch protection |
| Dispensation register | None granted this cycle | §9.11 |

## 9.3 Phase A — Architecture Vision

**Artefact:** Architecture Vision (`01-architecture-vision.md`), Stakeholder Map Matrix (below), Value Chain view (`02 §business`).

### Stakeholder Map Matrix

| Stakeholder | Key concern | Viewpoint addressed | Where answered |
|---|---|---|---|
| Accountable operations owner (shift boss) | "Am I still the one who decides?" | Approval and decision-rights viewpoint | `04 §4.5`, approval flow in the situation room |
| HSE / geotechnical authority | "Can this thing waive a control?" | Safety control viewpoint | `04 §4.4` tier table, `PR-05` |
| Maintenance planner | "Does it understand crew and equipment constraints?" | Reliability constraint viewpoint | `reliability_agent`, `ConstraintSet` |
| Enterprise architect | "Does this fit the target estate or is it a silo?" | Application and integration viewpoint | `02`, `05` |
| Data owner | "What data does it touch and at what classification?" | Data classification viewpoint | `04 §4.3`, `Evidence.dataClassification` |
| Model risk owner | "How do we know it did not degrade?" | Evaluation and drift viewpoint | `06 §6.4-6.5`, replay signature |
| Auditor / assurance | "Can the decision be reconstructed?" | Audit viewpoint | `04 §4.8`, `/v1/audit/{correlationId}` |
| Site IT / OT security | "Is there a path into the control network?" | Trust zone viewpoint | `04 §4.2`, `PR-05` |

### Business scenario (condensed)

**Problem.** During a shift, four systems each report a true fact in their own domain — plant reports a derate, fleet reports a truck down, weather reports a cell, CMMS reports a committed crew. No system holds the compound problem, so a human reconstructs it under time pressure while the decision window closes.

**Desired outcome.** One correlated incident, three genuinely different recovery options with explicit trade-offs, an accountable approval, and a reconstructable record.

**Human actors.** Shift boss (decides), dispatcher (executes), maintenance planner (constrains), HSE lead (owns controls).

**Measurable success.** `06 §6.5` metric set. This cycle instruments: constraint coverage, evidence coverage, prohibited-action violation rate (target 0), approval-bypass rate (target 0), replay match rate (target 100%).

## 9.4 Phase B — Business Architecture

**Artefacts:** Business Capability catalog, Business Process/Event diagram, Business Interaction matrix.

### Capability increment in scope

| Capability | Increment this cycle | Deferred |
|---|---|---|
| Operational signal correlation | Five synthetic event types into one incident | Real adapter ingestion, backfill, dedup at scale |
| Multi-domain constraint analysis | Reliability, operations, risk specialists | Geotech modelling, blending/grade control |
| Recovery option generation | Three ranked options with trade-offs | Optimiser-backed scheduling |
| Decision governance | Deterministic policy + scoped approval | Delegation chains, dual authorisation |
| Coordinated execution | Simulation-only work order and shift instruction | CMMS/dispatch adapters |
| Outcome verification | Projected outcome with residual risks | Closed-loop measurement from live production data |

### Business process (target sequence)

```text
Observe → Correlate → Assess → Generate options → Review policy
        → Obtain approval → Coordinate actions → Verify outcome
```

### Business Interaction Matrix (decision rights)

| Activity | Shift boss | Maintenance planner | HSE lead | CAIRN |
|---|---|---|---|---|
| Correlate signals | Informed | Informed | Informed | **Performs** |
| Generate options | Consulted | Consulted | Consulted | **Performs** |
| Determine permissibility | Informed | Informed | Accountable | **Applies the rule set** |
| Approve a Tier 3 action | **Accountable** | Accountable (work orders) | Consulted | Requests |
| Change a Tier 4 control | Not via CAIRN | Not via CAIRN | **Accountable via certified process** | **Prohibited** |
| Execute | Responsible | Responsible | Informed | Coordinates (simulated) |

## 9.5 Phase C — Information Systems Architecture: Data

**Artefacts:** Data Entity/Data Component catalog, Data Entity–Business Function matrix, Data classification model.

### Data Entity catalog

| Entity | Contract | Classification | Owner | Lifecycle |
|---|---|---|---|---|
| `OperationalEvent` | `05 §5.4` | INTERNAL | Source system owner | Immutable once received |
| `Evidence` | `app/domain/models.py` | PUBLIC→CRITICAL_OPERATIONAL | Data owner | Immutable, freshness-tracked |
| `SituationSummary` / `ConstraintSet` / `RiskAssessment` | `03 §3.8` | INTERNAL | Model risk owner | Per-run, replayable |
| `ScenarioOption` | `05 §5.5` | INTERNAL | Operations owner | Versioned; version binds the approval |
| `PolicyDecision` | `05` | INTERNAL | HSE / architecture | Immutable, policy-version stamped |
| `ApprovalRequest` | `05 §5.6` | RESTRICTED | Operations owner | State machine, expiring, single-use |
| `ActionRequest` / `ActionRecord` | `05 §5.7` | RESTRICTED | Operations owner | Idempotency-keyed, append-only |
| `OutcomeReport` | `03 §3.8` | INTERNAL | Operations owner | Per-run |
| `AuditEntry` | `04 §4.8` | RESTRICTED | Assurance | Append-only, sequence-ordered |

### Data Entity–Business Function matrix (abbreviated)

| Entity | Correlate | Assess | Option gen | Policy | Approve | Execute | Verify | Audit |
|---|---|---|---|---|---|---|---|---|
| OperationalEvent | C | R | R | – | – | – | R | R |
| Evidence | R | R | R | R | R | R | R | R |
| ScenarioOption | – | – | C | R | R | R | R | R |
| PolicyDecision | – | – | – | C | R | R | – | R |
| ApprovalRequest | – | – | – | – | C/U | R/U | – | R |
| ActionRecord | – | – | – | – | – | C | R | R |
| AuditEntry | C | C | C | C | C | C | C | R |

*C create · R read · U update. No entity is deleted; supersession replaces deletion.*

## 9.6 Phase C — Information Systems Architecture: Application

**Artefacts:** Application Portfolio catalog, Application Communication diagram, Application/Function matrix.

| Application component | Responsibility | Implementation | Enterprise substitute later |
|---|---|---|---|
| Situation room | Spatial decision interface | `app/web/` (Three.js + 2D fallback) | Enterprise ops console / Cesium for geospatial |
| Decision API | Typed boundary, error envelope | `app/api/main.py` (FastAPI) | API gateway + service mesh |
| Bounded agent graph | Specialist analysis and option generation | `app/agents/graph.py` (Strands `GraphBuilder`) | Same, on Bedrock AgentCore Runtime |
| Policy service | Deterministic permissibility | `app/policy/decisions.py` | Enterprise policy engine (OPA/Cedar) |
| Approval service | Scoped, expiring authorisation | `app/domain/run_service.py` | Enterprise workflow / identity-backed approvals |
| Action gateway | Only path to a state change | `app/tools/action_tools.py` | Integration platform with CMMS/dispatch adapters |
| Audit ledger | Append-only decision chain | `app/audit/ledger.py` | Immutable log store (QLDB-class / WORM) |
| Site read-model adapter | Read-only source integration | `app/integrations/fixture_source.py` | Governed Zone 1 adapters |

**Application/Function matrix note.** The gateway is the single choke point: no other component may produce an external effect. This is what makes `PR-04` and `PR-05` testable rather than aspirational.

## 9.7 Phase D — Technology Architecture

**Artefacts:** Technology Portfolio catalog, Environments and Locations diagram, Technology Standards catalog.

| Layer | This cycle | Standard / constraint | Rationale |
|---|---|---|---|
| Language / runtime | Python 3.12 | Pinned `>=3.12,<3.13` | 3.14 is ahead of dependency wheel support |
| Agent framework | Strands Agents SDK 1.54.0 | ADR-001, ADR-002 | Bounded `Graph`, model-provider abstraction, hooks |
| Model provider | Deterministic `FixtureModel`; Bedrock opt-in | ADR-001 | Demo must run with no credentials (`PR-06`) |
| API | FastAPI + Pydantic v2 | `05` contract-first | Schema is generated from the domain model |
| Presentation | Vanilla ES modules + vendored Three.js r169 | No build step | Removes toolchain and CDN as demo failure modes |
| Persistence | In-process stores | Prototype-only | Deliberate: state must reset cleanly for replay |
| Deployment | Local uvicorn | Prototype-only | AgentCore Runtime is the target, not this cycle |

### Environments

| Environment | Purpose | Credentials | Data |
|---|---|---|---|
| Local fixture | Demo, tests, evaluation | **None** | Synthetic only |
| Local bedrock (`CAIRN_MODE=bedrock`) | Model behaviour exploration | AWS | Synthetic only |
| Site integration | Not built this cycle | Would require Zone 1 governance | Not connected |

## 9.8 Phase E — Opportunities and Solutions

### Gap analysis (baseline → target)

| # | Gap | Severity | Resolution this cycle | Residual |
|---|---|---|---|---|
| G-01 | No system holds the compound problem | High | Correlation into one incident | Only five synthetic event types |
| G-02 | Trade-offs are implicit and undocumented | High | Three options with impacts, assumptions, constraints, evidence | Options are fixture-derived, not optimiser-derived |
| G-03 | Authorisation is informal | Critical | Deterministic policy + scoped expiring approval | No enterprise identity provider |
| G-04 | No prohibition boundary for high-consequence actions | Critical | Enumerated Tier 4 denial | Enforced in-process only |
| G-05 | Decisions cannot be reconstructed | High | Append-only audit + replay signature | In-memory ledger |
| G-06 | Duplicate/retried actions could double-apply | High | Idempotency claim before effect | Single-process store |
| G-07 | Stale and conflicting data silently resolved | High | Surfaced in read model, policy and UI | Two-source conflict only |
| G-08 | No spatial understanding of impact | Medium | 3D/2D scene driven by the read model | Stylised, not survey-accurate |
| G-09 | No production integration | Accepted | Out of scope by design | Requires Zone 1 programme |

### Solution building blocks delivered

`SBB-01` correlation · `SBB-02` bounded specialist graph · `SBB-03` option generation with provenance · `SBB-04` deterministic policy · `SBB-05` scoped approval · `SBB-06` idempotent simulated action gateway · `SBB-07` append-only audit · `SBB-08` spatial decision interface with fallback.

## 9.9 Phase F — Migration Planning

| Increment | Content | Entry condition | Exit condition |
|---|---|---|---|
| 0 (this cycle) | Vertical slice, synthetic, simulation-only | Architecture pack accepted | All suites pass; demo replays |
| 1 | Real model in the loop (Bedrock), evaluation harness with LLM-as-judge | Increment 0 green | Evaluation scores stable across prompt versions |
| 2 | Durable stores: audit ledger, action ledger, sessions | Increment 1 green | Replay works across process restarts |
| 3 | One governed read-only adapter (weather is the lowest-risk first source) | Zone 1 review passed | No write path introduced; classification enforced |
| 4 | Draft artefacts into a real CMMS sandbox behind the same gateway | Increment 3 green + data owner sign-off | Tier 3 only; Tier 4 remains prohibited |
| — | Any Tier 4 capability | **Not on the roadmap** | Requires a separate certified control programme |

**Transition constraint.** No increment may widen the action tier without a new ADR and an HSE authority decision. Increments may add sources and durability freely; they may not add authority.

## 9.10 Phase G — Implementation Governance

**Architecture Contract with the implementation agent:** `07-claude-code-handoff.md` (non-negotiable engineering rules) plus `08-visual-demo-plan.md` (visual acceptance).

### Compliance assessment for increment 0

| Requirement | Source | Status | Evidence |
|---|---|---|---|
| Strands for the agent layer, no LangGraph/CrewAI/unbounded loop | `07` | Met | `app/agents/graph.py` uses `GraphBuilder` with max executions and timeouts |
| Model is not the authorisation boundary | `PR-01`, ADR-003 | Met | Policy is a pure function; denial test asserts no graph call |
| No live systems or proprietary credentials | `07`, `04 §4.9` | Met | `/healthz` reports `credentialsRequired: false` |
| No direct OT control path | `PR-05` | Met | Tier 4 enumerated and denied for all roles |
| Read/proposal/state-changing tools separated | `07` | Met | Three modules; only the gateway commits |
| Typed structured outputs at every agent boundary | `03 §3.8` | Met | `structured_output_model` on every node |
| Idempotency key + approval token on every state change | `07` | Met | Gateway refuses without both; replay test asserts no second artefact |
| Synthetic data with deterministic seed | `07` | Met | `fixtures/scenarios/compound-disruption.json`, replay signature equality |
| Fail closed | `PR-02` | Met | Fail-closed, expiry and stale-evidence tests |
| No raw chain-of-thought displayed | `08` | Met | `test_no_chain_of_thought_field_is_exposed` |
| 2D fallback usable | `08 §8.8` | Met | Browser walkthrough captured in both renderers |
| Durable stores | `02` | **Not met — deferred** | In-memory by design; increment 2 |
| Enterprise identity | `04` | **Not met — deferred** | Roles are configuration, not federated identity |

### Open compliance risks

| ID | Risk | Impact | Treatment |
|---|---|---|---|
| CR-01 | Roles come from configuration, not an IdP | An operator could self-assign a role locally | Accepted for prototype; increment 1 binds to identity |
| CR-02 | Audit ledger is in-process | Audit is lost on restart | Accepted for prototype; increment 2 |
| CR-03 | Option economics are fixture-derived | Numbers are illustrative, not modelled | Stated in README and in-app `SIMULATION ONLY` badge |
| CR-04 | Determinism is provided by a fixture model | Real-model behaviour is unproven | Increment 1 runs the evaluation suite against Bedrock |

## 9.11 Phase H — Architecture Change Management

| Change class | Example | Response |
|---|---|---|
| Simplification | Prompt wording, scene styling | Implement; no architecture change |
| Incremental | New event type, new read source | Update `05`, extend fixtures, re-run suites |
| Re-architecting | Adding a write path to a live system, changing the action tier model, replacing Strands | **New ADR + Phase A re-entry** |

**Change triggers monitored:** replay signature drift, prohibited-action violation rate above zero, approval-bypass rate above zero, evaluation score regression across prompt or model versions.

**Dispensations granted this cycle:** none.

## 9.12 Requirements Management (continuous)

### Architecture Requirements Specification — increment 0

| ID | Requirement | Type | Priority | Verification | Status |
|---|---|---|---|---|---|
| AR-01 | Correlate ≥4 heterogeneous signals into one incident | Functional | Must | `test_five_signals_become_one_incident` | Met |
| AR-02 | Produce ≥3 options differing in what they trade away | Functional | Must | `test_options_are_meaningfully_different` | Met |
| AR-03 | Each option exposes impact, recovery time, risk, assumptions, constraints, evidence, confidence, approval | Functional | Must | `test_every_scenario_exposes_the_required_decision_fields` | Met |
| AR-04 | No option may trade away a standing safety control | Constraint | Must | `test_every_option_respects_the_standing_ramp_closure_control` | Met |
| AR-05 | Deny every Tier 4 action for every role without a model call | Non-functional (safety) | Must | `test_tier_four_is_denied_for_every_role` | Met |
| AR-06 | Refuse a state change without a valid, unexpired, in-scope approval | Non-functional (safety) | Must | `tests/safety/test_approval.py` | Met |
| AR-07 | Replay a duplicate action without a second effect | Non-functional (integrity) | Must | `test_duplicate_action_replays_without_a_new_side_effect` | Met |
| AR-08 | Surface stale and conflicting evidence without resolving it silently | Non-functional (integrity) | Must | `tests/safety/test_evidence.py` | Met |
| AR-09 | Identical replay from a clean reset | Non-functional (assurance) | Must | `tests/evaluation/test_replay.py` | Met |
| AR-10 | Reconstruct the full chain from event to outcome | Non-functional (auditability) | Must | `test_audit_reconstructs_the_whole_chain` | Met |
| AR-11 | Run with no cloud credentials | Constraint | Must | `test_health_needs_no_credentials` | Met |
| AR-12 | Remain usable without WebGL | Non-functional (availability) | Should | Browser walkthrough, both renderers | Met |
| AR-13 | Never display raw chain-of-thought | Constraint | Must | `test_no_chain_of_thought_field_is_exposed` | Met |
| AR-14 | Scene legible within two seconds | Non-functional (usability) | Should | Labelled scene, five-tile KPI strip | Met, subjective |
| AR-15 | Survive process restart with audit intact | Non-functional (durability) | Could | — | **Deferred to increment 2** |

### Traceability summary

```text
Stakeholder concern → Principle → Requirement → Building block → Component → Test
      (§9.3)           (§9.2)      (§9.12)        (§9.8)          (§9.6)    (tests/)
```

Worked example: *"Can this thing waive a safety control?"* (HSE authority, §9.3) → `PR-05` no direct OT control path (§9.2) → `AR-05` deny every Tier 4 action for every role (§9.12) → `SBB-04` deterministic policy (§9.8) → `app/policy/decisions.py` (§9.6) → `test_tier_four_is_denied_for_every_role` (green).

## 9.13 What this cycle does not claim

- It is not a production mine-control system and carries no operational certification.
- The economics on the option cards are illustrative fixtures, not a modelled mine plan.
- Determinism in this increment comes from a fixture model provider; real-model behaviour is an increment 1 question.
- No integration with fleet management, plant control, ERP, CMMS or MineRP-class platforms exists or is implied.
