# 5. Interfaces and Data Contracts

## 5.1 Contract-first rule

The public boundary is the contract. Implementations may change behind it, but callers should not depend on prompt wording, model output prose, internal Strands objects, or vendor-specific response shapes.

All external input and third-party responses are untrusted and must be validated at the boundary. Use typed Pydantic models in Python and emit JSON Schema/OpenAPI from those models.

## 5.2 API surface

The initial service can expose a small REST API. Long-running workflows should return `202 Accepted` with a run resource rather than blocking a request.

| Method | Resource | Purpose |
|---|---|---|
| `POST` | `/v1/runs` | Start a bounded analysis or recovery run |
| `GET` | `/v1/runs/{runId}` | Retrieve run status and result references |
| `POST` | `/v1/events` | Ingest a validated operational event |
| `GET` | `/v1/incidents/{incidentId}` | Retrieve the current incident view |
| `GET` | `/v1/scenarios/{scenarioId}` | Retrieve ranked options and evidence |
| `POST` | `/v1/approvals` | Approve, reject, or request revision |
| `GET` | `/v1/actions/{actionId}` | Retrieve action and outcome status |
| `POST` | `/v1/actions/{actionId}/reconcile` | Resolve an unknown external outcome |
| `GET` | `/v1/audit/{correlationId}` | Retrieve the decision trace for an authorised user |

## 5.3 Common envelope

```json
{
  "schemaVersion": "1.0",
  "correlationId": "corr_01J...",
  "tenantId": "demo-mining-co",
  "siteId": "site_pilbara_01",
  "occurredAt": "2026-09-06T10:19:00Z",
  "producer": "fleet-adapter",
  "dataClassification": "INTERNAL",
  "payload": {}
}
```

Required rules:

- All timestamps are UTC ISO-8601 values.
- IDs are opaque strings; do not expose database keys as public semantics.
- `schemaVersion` is additive and explicitly versioned.
- `correlationId` is propagated across agent nodes, tools, events, approvals, and audit records.
- `dataClassification` is required at the edge.

## 5.4 Operational event

```json
{
  "eventId": "evt_01J...",
  "eventType": "ASSET_DEGRADED",
  "source": {
    "system": "plant-simulator",
    "sourceRecordId": "plant-42-20260906-1015",
    "observedAt": "2026-09-06T10:15:00Z",
    "receivedAt": "2026-09-06T10:15:03Z"
  },
  "siteId": "site_pilbara_01",
  "assetId": "asset_primary_crusher_01",
  "locationId": "loc_crusher_01",
  "severity": "HIGH",
  "status": "OPEN",
  "measurements": {
    "capacityPercent": 55,
    "nominalCapacityPercent": 100
  },
  "freshnessSeconds": 3,
  "evidenceIds": ["evd_01J..."],
  "metadata": {}
}
```

Minimum event types for the demo:

- `ASSET_DEGRADED`
- `ASSET_UNAVAILABLE`
- `WEATHER_ALERT`
- `MAINTENANCE_CONSTRAINT`
- `PERMIT_CONFLICT`
- `PRODUCTION_CONSTRAINT`
- `ACTION_COMPLETED`
- `ACTION_FAILED`

## 5.5 Scenario option

```json
{
  "scenarioId": "scn_01J...",
  "scenarioVersion": 3,
  "title": "Protect crusher feed and preserve storm buffer",
  "status": "PROPOSED",
  "objectiveWeights": {
    "safety": 1.0,
    "throughput": 0.8,
    "schedule": 0.6,
    "maintenance": 0.7,
    "energy": 0.4
  },
  "assumptions": [
    "Truck 204 remains unavailable for the next 90 minutes"
  ],
  "unknowns": [
    "Actual storm arrival may vary by 20 minutes"
  ],
  "impacts": {
    "estimatedThroughputDelta": -0.12,
    "estimatedRecoveryMinutes": 75,
    "affectedAssets": ["asset_primary_crusher_01", "asset_truck_204"]
  },
  "riskFindings": ["risk_01J..."],
  "requiredApprovals": ["SHIFT_BOSS", "MAINTENANCE_PLANNER"],
  "evidenceIds": ["evd_01J...", "evd_01K..."]
}
```

Agents must return a list of options, not only a single recommendation. The recommendation must state why it wins under the supplied objective weights and what would change the result.

## 5.6 Approval request

```json
{
  "approvalId": "apr_01J...",
  "correlationId": "corr_01J...",
  "scenarioId": "scn_01J...",
  "scenarioVersion": 3,
  "requestedActionTypes": ["CREATE_WORK_ORDER", "PUBLISH_SHIFT_INSTRUCTION"],
  "scope": {
    "siteId": "site_pilbara_01",
    "assetIds": ["asset_primary_crusher_01", "asset_truck_204"]
  },
  "requiredRoles": ["SHIFT_BOSS"],
  "expiresAt": "2026-09-06T10:45:00Z",
  "policyDecisionId": "pol_01J...",
  "status": "PENDING"
}
```

Approval transitions:

```text
PENDING → APPROVED → CONSUMED
        ↘ REJECTED
        ↘ EXPIRED
        ↘ SUPERSEDED
```

## 5.7 Action request

```json
{
  "actionId": "act_01J...",
  "actionType": "CREATE_WORK_ORDER",
  "approvalToken": "opaque-server-token",
  "idempotencyKey": "act:v1:scn_01J:work-order:crusher-inspection",
  "actorId": "user_shift_boss_01",
  "policyDecisionId": "pol_01J...",
  "correlationId": "corr_01J...",
  "expectedVersion": 4,
  "payload": {
    "assetId": "asset_primary_crusher_01",
    "priority": "HIGH",
    "description": "Inspect derated crusher before next operating window"
  }
}
```

Action states:

```text
PLANNED → APPROVAL_REQUIRED → APPROVED → IN_PROGRESS → SUCCEEDED
                              ↘ REJECTED
                              ↘ EXPIRED
                              ↘ UNKNOWN → RECONCILING → SUCCEEDED / FAILED
```

## 5.8 Error contract

Every API error uses the same shape:

```json
{
  "error": {
    "code": "POLICY_DENIED",
    "message": "The requested action requires HSE approval",
    "details": {
      "requiredRoles": ["HSE_LEAD"]
    },
    "correlationId": "corr_01J..."
  }
}
```

Suggested status mapping:

- `400` malformed request
- `401` unauthenticated
- `403` unauthorised or policy denied
- `404` resource not found
- `409` version conflict or idempotency conflict
- `422` semantically invalid data
- `429` rate or budget limit
- `500` unexpected internal error
- `503` dependency unavailable

## 5.9 Idempotency contract

State-changing calls must accept and honour an idempotency key.

- The caller creates the key and reuses it for retries.
- The action store atomically claims the key before calling the external system.
- The request body hash is stored and compared on replay.
- The same key with a different payload returns `409` or `422`; it never replays the wrong response.
- An in-flight duplicate returns `409` or a bounded `202` status response by deliberate policy.
- The key retention period exceeds the longest retry and dead-letter replay path.

## 5.10 Agent/tool interface

```python
class OperationalTool(Protocol):
    name: str
    read_only: bool
    required_roles: tuple[str, ...]

    async def execute(
        self,
        request: ToolRequest,
        context: ExecutionContext,
    ) -> ToolResult: ...
```

`ToolResult` must include `status`, `evidenceIds`, `sourceRecordIds`, `observedAt`, `correlationId`, and an explicit `unknown` or `stale` indicator where appropriate.

## 5.11 Compatibility rules

- Add optional fields rather than changing field types or removing fields.
- Keep one active contract version where possible.
- Version prompts, tools, policies, and schemas together in the audit record.
- Do not expose Strands `AgentResult`, internal model messages, or raw provider payloads as stable application APIs.
