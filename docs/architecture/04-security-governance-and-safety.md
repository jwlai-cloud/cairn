# 4. Security, Governance, and Safety

## 4.1 Security posture

CAIRN is an enterprise decision-support and coordination system for a high-consequence environment. The design assumes that operational data, documents, telemetry, tool responses, and user messages may be incomplete, stale, malicious, or instruction-like.

The model is not the security boundary. The security boundary is the combination of identity, policy, tool gateway, data access controls, approval service, network boundary, and audit ledger.

AWS guidance recommends least privilege, encryption, lineage, immutable audit logs, and trace IDs for generative AI data and agent decision chains. See [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-data-considerations-gen-ai/security.html).

## 4.2 Trust zones

```text
Zone 0: Operational technology
  PLCs, safety systems, control networks, autonomous equipment
  CAIRN has no direct control path in the MVP.

Zone 1: Site integration boundary
  Approved read adapters, data diode/API gateway, event validation, buffering

Zone 2: Enterprise data and agent platform
  Event store, evidence store, Strands runtime, policy, approvals, audit

Zone 3: User and collaboration surfaces
  Situation room, approval inbox, shift brief, notifications
```

The only permitted path from CAIRN to an external operational system is through a typed action gateway with authorization, policy, approval, idempotency, and audit checks.

## 4.3 Data classification

| Class | Examples | Controls |
|---|---|---|
| Public | Public weather, generic standards, published mine information | Integrity and source attribution |
| Internal | Shift plans, equipment status, operating procedures | Role-based access and encryption |
| Restricted | Personnel, incident details, contractor records, commercial schedules | Fine-grained authorization, minimisation, redaction |
| Critical operational | Safety controls, isolation states, geotechnical risk, emergency data | Explicit scope, dual review where required, no model-only action |

The agent receives only the minimum data needed for the current task. Sensitive source payloads should be referenced by `evidenceId` rather than copied into prompts unnecessarily.

## 4.4 Action autonomy tiers

| Tier | Examples | Default handling |
|---|---|---|
| 0 — Observe | Retrieve status, search evidence, summarise events | Automated if authorised |
| 1 — Analyse | Correlate events, calculate impacts, generate scenarios | Automated with evidence and confidence |
| 2 — Draft | Draft work order, shift brief, escalation, notification | Requires review before publication |
| 3 — Commit | Create an approved work order or internal task | Human approval plus policy token |
| 4 — High consequence | Change production control, safety control, permit, blast, isolation, emergency instruction | Prohibited for CAIRN MVP; separate certified control process required |

## 4.5 Approval model

An approval is a signed, scoped authorisation, not a Boolean flag.

It must include:

- `approvalId`
- `approverId` and role
- `scope` of permitted action
- `siteId` and affected assets
- `policyDecisionId`
- `planVersion`
- `expiresAt`
- `conditions`
- `correlationId`
- timestamp and audit metadata

Approval must be invalidated if the plan, evidence set, affected asset, policy version, or expected state changes materially.

## 4.6 Threat model

### Prompt injection from operational data

Telemetry, documents, tickets, and third-party responses are data, not instructions. Delimit them, validate their shape, strip executable content where appropriate, and keep tool authorization outside the model.

### Over-permissioned tools

Every agent receives a node-specific tool allow-list. Read and write tools are separate interfaces. A write tool cannot be reached by a read-only specialist through prompt wording.

### Stale or conflicting data

Every event includes source time, observed time, freshness, source reliability, and version. Conflicts create an explicit finding and may block an action.

### Model hallucination

Require evidence IDs, assumptions, unknowns, and confidence. Reject structured output that omits required provenance. Never treat a fluent explanation as operational evidence.

### Replay and duplicate execution

Use idempotency keys, an action ledger, atomic claim of action intent, and explicit `UNKNOWN` state when a timeout leaves effect status uncertain.

### Data exfiltration

Use role-scoped retrieval, field-level redaction, output filtering, egress controls, encryption in transit and at rest, and alerts for unusual retrieval or tool behaviour.

### Model or prompt change

Version models, prompts, tools, schemas, policies, and retrieval configurations. A change must pass the scenario evaluation suite before it is promoted.

## 4.7 Governance responsibilities

| Role | Responsibility |
|---|---|
| Product owner | Prioritises use cases and accepts business outcomes |
| Accountable operations owner | Owns decision rights and action approval |
| HSE / geotechnical authority | Defines prohibited actions and hazard controls |
| Enterprise architect | Maintains target architecture, standards, and roadmap |
| Data owner | Defines source quality, access, retention, and stewardship |
| Platform owner | Runs Strands/AWS runtime, identity, monitoring, and release controls |
| Model risk owner | Maintains evaluation, red-team, drift, and change evidence |
| Auditor / assurance | Reviews decision traces, controls, and exceptions |

## 4.8 Audit record

For each run, retain:

1. User/request identity and role.
2. Input event IDs and retrieval timestamps.
3. Model ID, provider, temperature/configuration, and prompt version.
4. Agent/node sequence and tool calls.
5. Tool request and response hashes.
6. Evidence references and source classifications.
7. Policy decisions and approval requests.
8. Human decision and conditions.
9. Action result, idempotency outcome, and post-action evidence.
10. Final outcome, unresolved items, latency, token usage, and cost estimate.

The audit record must be append-only to application users and must support replay without requiring the original conversational state.

## 4.9 Safety case for the prototype

The prototype is safe to demonstrate if:

- All events are synthetic or explicitly approved non-production data.
- All state-changing tools write to a simulation or draft store.
- The UI makes approval status and uncertainty visible.
- Prohibited actions are tested as negative cases.
- The demo never implies production certification.
- The system fails closed when authorization, policy, or evidence validation is unavailable.
