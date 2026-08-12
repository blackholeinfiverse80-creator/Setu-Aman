# SETU Connector Runtime Contracts — Frozen Specification v1.0

**Status:** FROZEN — no changes to contract structure
**Live Integration:** CERTIFIED (65/65 tests passing)
**Production:** Pending Alay + Rayyan sign-off

---

## Contract vs Integration Status

| Contract Area | Contract Status | Integration Status |
|---|---|---|
| Authentication | Frozen v1.0 | Proven — valid, invalid, missing paths all tested |
| API fetch/normalize | Frozen v1.0 | Proven — success, timeout, malformed, missing field |
| MDU normalization | Frozen v1.0 | Proven — all fields, stable IDs, stable keys |
| MasterDB persistence | Frozen v1.0 | Proven — SQLite restart, idempotency |
| InsightFlow dispatch | Frozen v1.0 | Proven — dispatch log verified |
| Replay | Frozen v1.0 | Proven — hash stability, idempotency |
| Tenant isolation | Frozen v1.0 | Proven — zero cross-contamination |
| Failure path | Frozen v1.0 | Proven — error captured with trace_id |

---

## 1. Authentication Contract

Every connector declares its auth_scheme in its manifest. Credentials are injected via environment variables through the auth boundary (`connectors/bright_connection/auth.py`). SETU runtime never stores or processes credentials.

**Supported schemes:**

| Scheme | Required Config Keys | Env Variable |
|---|---|---|
| api_key | api_key, base_url | SETU_{CONNECTOR}_API_KEY, SETU_{CONNECTOR}_BASE_URL |
| oauth2 | oauth_token | SETU_CRM_OAUTH_TOKEN |
| basic | username, password, base_url | connector-specific |
| none | — | — |

**Contract:**
- `authenticate()` returns `True` on success
- `authenticate()` raises `ValueError` on missing credentials — never silently fails
- `authenticate()` raises `RuntimeError` on 401 from real API
- Auth credentials never stored in MDURecord or event payloads
- Stub mode activates automatically when env vars absent — explicitly flagged as `_stub_mode: True`

---

## 2. API Contract

**Fetch interface:**
```
fetch_data(entity_type: str, params: Optional[dict]) -> List[dict]
```

- Real HTTP path: `GET {base_url}/{entity_type}` with auth header
- Stub path: contract-shaped sample records when credentials absent
- Raises `RuntimeError` on API failure — never returns partial/corrupt data silently
- Timeout: 30 seconds (configurable)

**Normalize interface:**
```
normalize(raw_record: dict, entity_type: str) -> MDURecord
```

- One raw record in, one MDURecord out
- Field mapping only — no computation, no business logic
- `entity_id` is stable and unique within tenant scope
- Missing fields produce empty string entity_id — never crash

---

## 3. MDU Record Contract

Every record flowing through the runtime carries these fields — all proven stable:

| Field | Immutable | Proven |
|---|---|---|
| tenant_id | YES | Isolation test — zero cross-contamination |
| trace_id | YES | E2E test — present in all records |
| entity_id | YES | Stability test — same input same ID |
| source_connector | YES | Provenance test — preserved through restart |
| ingested_at | YES | E2E test — present in all records |
| idempotency_key | YES | Stability test — same input same key (32 chars) |
| schema_version | YES | Persistence test — preserved through restart |
| integrity_hash | Computed | Replay test — identical across replays |
| canonical_data | Normalized | Normalization test — all fields mapped |

---

## 4. MasterDB Integration Boundary

**Current backends:**

| Backend | Env Var | Status |
|---|---|---|
| memory | `SETU_MASTERDB_BACKEND=memory` | Active — validate_runtime.py |
| sqlite | `SETU_MASTERDB_BACKEND=sqlite` | Active — integration/persistence proof |
| mongodb | `SETU_MASTERDB_BACKEND=mongodb` | Stub — KAVY adapter required |

**Proven properties:**
- Tenant isolation: records partitioned by tenant_id, no cross-reads
- Idempotent upsert: same idempotency_key never creates duplicate
- Persistence: SQLite records survive process restart
- Provenance: source_connector, schema_version, ingested_at preserved
- Schema compatibility: MDURecord.to_dict() / from_dict() round-trip verified

**Production boundary note:** MongoDB backend is owned by KAVY/MDU. Replace `_MongoDBStore` stub in `runtime/masterdb.py` with KAVY-provided adapter. Interface is identical — no other code changes needed.

---

## 5. Event Contract

All connector lifecycle events published as `ConnectorEvent`:

```json
{
  "event_id": "evt_<16-char-hex>",
  "event_type": "sync_completed",
  "connector_id": "bright_orders",
  "tenant_id": "tenant_bright_connection_001",
  "trace_id": "trace_<tenant>_<12-char-hex>",
  "timestamp": "2025-01-15T10:30:00Z",
  "payload": {"records_ingested": 3, "records_failed": 0},
  "schema_version": "1.0"
}
```

---

## 6. Error Contract

All connector errors published as `ConnectorError`:

```json
{
  "error_id": "err_<16-char-hex>",
  "error_code": "external_system_error",
  "connector_id": "bright_orders",
  "tenant_id": "tenant_bright_connection_001",
  "trace_id": "trace_...",
  "message": "bright_orders requires api_key",
  "timestamp": "2025-01-15T10:30:00Z",
  "retryable": true,
  "attempt": 1
}
```

**Proven error codes:**

| Code | Retryable | Proven |
|---|---|---|
| auth_failed | No | Missing credentials test |
| timeout | Yes | Non-routable IP test |
| external_system_error | Yes | Missing api_key failure path test |
| schema_mismatch | No | Malformed response test |
| tenant_mismatch | No | Isolation contract |

---

## 7. Replay Contract

**Proven properties:**
1. Original ingestion registers record in ReplayEngine by idempotency_key
2. `replay(tenant_id, idempotency_key)` returns the exact same MDURecord
3. `record.integrity_hash()` is identical on original and replayed record
4. Replaying the same key twice produces identical output (deterministic)
5. Duplicate upsert to MasterDB does not create a second canonical record

---

## 8. Tenant Isolation Contract

**Proven:**
- Two tenants (`tenant_bright_connection_001`, `tenant_integration_test_002`) run simultaneously
- Records in tenant A carry only tenant A's tenant_id
- Records in tenant B carry only tenant B's tenant_id
- `masterdb.list_by_type(tenant_A, ...)` never returns tenant B records
- Intersection of tenant ID sets is empty

---

## 9. Retry Contract

Default retry policy (per connector manifest):

```json
{
  "max_attempts": 3,
  "backoff_seconds": [1, 5, 15],
  "retryable_errors": ["timeout", "rate_limit", "server_error"]
}
```

---

## 10. Connector Independence Guarantee

A connector is independently replaceable when:
1. `connector_id` unchanged
2. `supported_entity_types` unchanged
3. `normalize()` output produces identical `canonical_data` structure
4. `manifest.version` bumped

SETU core requires no modification when a connector is replaced.
All 9 Bright Connection connectors satisfy this guarantee.
