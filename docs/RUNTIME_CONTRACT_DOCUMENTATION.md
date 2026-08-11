# SETU Connector Runtime Contracts — Frozen Specification v1.0

## Overview

Runtime contracts define the exact interface between external systems and the SETU Enterprise Operating System. Every connector must comply with these contracts. Contracts are frozen — connectors are independently replaceable without modifying SETU core.

---

## 1. Authentication Contract

Every connector declares its auth_scheme in its manifest. SETU runtime reads auth config from tenant config JSON and passes it to the connector instance. SETU never stores or processes credentials — it passes them opaquely.

**Supported schemes:**

| Scheme | Required Config Keys | Notes |
|---|---|---|
| api_key | api_key, base_url | Header: Authorization: Bearer {api_key} |
| oauth2 | oauth_token | Or client_id + client_secret + token_url for token refresh |
| basic | username, password, base_url | HTTP Basic Auth |
| none | — | Public endpoints |
| custom | connector-defined | Connector handles auth internally |

**Contract:**
- `authenticate()` returns `True` on success
- `authenticate()` raises `ValueError` or `ConnectionError` on failure — never silently fails
- Auth credentials are never stored in MDURecord or event payloads

---

## 2. API Contract

**Fetch interface:**
```
fetch_data(entity_type: str, params: Optional[dict]) -> List[dict]
```

- `entity_type` is always a valid `MDUEntityType` value
- `params` is optional — used for date ranges, pagination, filters
- Returns raw dicts — normalization is separate
- Raises `ConnectorError` on API failure — never returns partial/corrupt data silently

**Normalize interface:**
```
normalize(raw_record: dict, entity_type: str) -> MDURecord
```

- One raw record in, one MDURecord out
- Field mapping only — no computation, no business logic
- `entity_id` must be stable and unique within tenant scope
- `canonical_data` must contain only normalized fields — no raw system IDs leaking through except as `raw_ref`

---

## 3. Event Contract

All connector lifecycle events are published as `ConnectorEvent`:

```json
{
  "event_id": "evt_<16-char-hex>",
  "event_type": "sync_completed",
  "connector_id": "bright_orders",
  "tenant_id": "tenant_bright_connection_001",
  "trace_id": "trace_<tenant>_<12-char-hex>",
  "timestamp": "2025-01-15T10:30:00Z",
  "payload": {
    "records_ingested": 3,
    "records_failed": 0
  },
  "schema_version": "1.0"
}
```

**Event types and when they fire:**

| Event | Trigger |
|---|---|
| sync_started | Before fetch_data is called |
| data_received | After each entity_type batch is normalized |
| sync_completed | After all entity_types processed |
| sync_failed | On unrecoverable error |
| auth_success | After successful authenticate() |
| auth_failed | After failed authenticate() |
| webhook_received | When external system pushes data |
| file_imported | After CSV/Excel import completes |
| retry_attempted | On each retry attempt |
| connector_degraded | When connector enters degraded state |

---

## 4. Webhook Contract

Connectors that support webhooks (`supports_webhook: true`) must:

- Accept POST requests at `/connectors/{connector_id}/webhook`
- Validate webhook signature using connector-specific secret
- Parse payload into raw records
- Call `normalize()` on each record
- Publish `webhook_received` event
- Return HTTP 200 immediately — processing is async

**Webhook payload envelope:**
```json
{
  "connector_id": "bright_crm",
  "tenant_id": "tenant_bright_connection_001",
  "event_type": "visit_created",
  "timestamp": "2025-01-15T10:30:00Z",
  "records": [{ ... }]
}
```

---

## 5. File Import Contract

Connectors that support file import (`supports_file_import: true`) must:

- Accept CSV or Excel files
- Map columns to raw record fields using a column mapping config
- Call `normalize()` on each row
- Publish `file_imported` event with row count
- Reject files with missing required columns — never silently skip rows

**Column mapping config (in tenant config):**
```json
{
  "connector_id": "bright_inventory",
  "file_import": {
    "format": "csv",
    "column_map": {
      "Item Code": "sku",
      "Warehouse": "warehouse_code",
      "Available Qty": "qty_available"
    }
  }
}
```

---

## 6. Metadata Contract

Every MDURecord carries standard metadata:

| Field | Immutable | Description |
|---|---|---|
| tenant_id | YES | Never changes after creation |
| trace_id | YES | Shared across the operational chain |
| entity_id | YES | Stable external identifier |
| source_connector | YES | Origin connector — never overwritten |
| ingested_at | YES | Set at normalization time |
| idempotency_key | YES | Computed from tenant+type+entity+connector |
| schema_version | YES | Contract version |
| integrity_hash | Computed | SHA-256 of canonical_data — recomputed on demand |

---

## 7. Versioning Contract

- Current contract version: `1.0`
- `schema_version` field is present in every MDURecord and ConnectorEvent
- Connectors declare their implementation version in `manifest.version`
- Version upgrades are additive — new optional fields only
- Breaking changes require a new schema_version negotiated by policy
- SETU runtime rejects records with unknown schema_version

---

## 8. Error Handling Contract

All connector errors are published as `ConnectorError`:

```json
{
  "error_id": "err_<16-char-hex>",
  "error_code": "timeout",
  "connector_id": "biz_analyst",
  "tenant_id": "tenant_bright_connection_001",
  "trace_id": "trace_...",
  "message": "Connection timed out after 30s",
  "timestamp": "2025-01-15T10:30:00Z",
  "retryable": true,
  "details": { "endpoint": "/orders", "attempt": 2 },
  "attempt": 2
}
```

**Error codes:**

| Code | Retryable | Description |
|---|---|---|
| auth_failed | No | Credentials invalid or expired |
| timeout | Yes | External system did not respond |
| rate_limited | Yes | External system rate limit hit |
| schema_mismatch | No | External system changed its schema |
| missing_field | No | Required field absent in raw record |
| external_system_error | Yes | 5xx from external system |
| normalization_failed | No | normalize() raised an exception |
| contract_violation | No | MDURecord invariant violated |
| tenant_mismatch | No | Record tenant_id != connector tenant_id |

---

## 9. Retry Contract

Default retry policy (overridable per connector in manifest):

```json
{
  "max_attempts": 3,
  "backoff_seconds": [1, 5, 15],
  "retryable_errors": ["timeout", "rate_limit", "server_error"]
}
```

- Retry is only attempted for `retryable: true` errors
- Each retry publishes a `retry_attempted` event
- After max_attempts, connector transitions to `degraded` status
- Idempotency_key ensures duplicate records are not created on retry

---

## 10. Tenant Isolation Contract

- `tenant_id` is set at connector instantiation and is immutable
- Every MDURecord carries `tenant_id` — enforced by pipeline before MasterDB write
- MasterDB is partitioned by `tenant_id` — no cross-tenant reads
- Replay is scoped to `tenant_id`
- ConnectorRegistry creates separate instances per tenant — no shared state
- A `tenant_mismatch` error is raised (non-retryable) if record.tenant_id != connector.tenant_id

---

## Connector Independence Guarantee

A connector is considered independently replaceable when:

1. Its `connector_id` is unchanged
2. Its `supported_entity_types` are unchanged
3. Its `normalize()` output produces identical `canonical_data` structure
4. Its `manifest.version` is bumped

SETU core requires no modification when a connector is replaced.
