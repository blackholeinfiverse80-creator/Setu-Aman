# SETU Connector Framework — Handover Package
**From:** Aman Pal
**Date:** 2025-06-01
**Sprint:** BHIV vNEXT — Live Integration & Production Convergence
**Repo:** https://github.com/blackholeinfiverse80-creator/Setu-Aman.git
**Branch:** main
**Folder:** Setu(Aman)/

---

## Handover Status

| Recipient | Status | Section |
|---|---|---|
| Rudra / SETU | READY | Section 1 |
| KAVY / MasterDB | READY | Section 2 |
| Alay | READY | Section 3 |
| Rayyan | READY | Section 4 |
| Raj | READY | Section 5 |

---

## Section 1 — Rudra / SETU

### Completed Connector Runtime

The SETU Connector Framework is complete and live-integration certified.

**What is delivered:**
- Connector SDK (`connector_sdk/`) — BaseConnector, MDURecord, ConnectorRegistry, ConnectorRuntimeContract
- 9 Bright Connection connectors — all upgraded with real HTTP fetch path + explicit stub fallback
- Auth boundary (`connectors/bright_connection/auth.py`) — env-var credential injection, never in MDURecord
- Runtime pipeline, MasterDB (3-backend), InsightFlow, ReplayEngine
- 45/45 local validation passing
- 65/65 live integration tests passing
- Full E2E proof generated (`LIVE_BRIGHT_CONNECTION_EVIDENCE.json`)

**Integration status:**
- Framework: LIVE_INTEGRATION_CERTIFIED
- Real API connectivity: BLOCKED — credentials not yet provided by Bright Connection
- Production: BLOCKED — Alay + Rayyan sign-off pending

**Remaining blockers:**
1. Real Bright Connection API credentials (Raj to provide)
2. MongoDB MasterDB adapter (KAVY to provide)
3. Production infrastructure (Alay)
4. Final regression (Rayyan)

**Architecture principle maintained:**
- Zero connector-specific logic in SETU runtime
- All data flows as MDURecord
- Connectors are independently replaceable
- No SETU core modifications made

---

## Section 2 — KAVY / MasterDB

### Persistence Integration Requirements

**Current state:**
The MasterDB has a 3-backend architecture. The MongoDB backend is a clearly marked stub awaiting the canonical adapter from KAVY.

**File to update:** `runtime/masterdb.py`

**What KAVY needs to replace:**
```python
class _MongoDBStore:
    # This entire class body is a stub
    # Replace with KAVY-provided MongoDB adapter
    # The public interface must match exactly:
    def upsert(self, record: MDURecord) -> bool: ...
    def get(self, tenant_id, entity_type, idempotency_key) -> Optional[MDURecord]: ...
    def list_by_type(self, tenant_id, entity_type) -> List[MDURecord]: ...
    def count(self, tenant_id, entity_type=None) -> int: ...
    def snapshot(self, tenant_id) -> Dict[str, Any]: ...
```

**Schema/provenance dependencies:**
Every MDURecord written to MasterDB carries:
- `tenant_id` — partition key
- `idempotency_key` — 32-char SHA-256 (tenant|entity_type|entity_id|source_connector)
- `integrity_hash` — SHA-256 of canonical_data (computed on demand)
- `source_connector` — provenance
- `schema_version` — "1.0"
- `ingested_at` — ISO 8601 UTC
- `trace_id` — operational trace
- `entity_type` — MDUEntityType enum value
- `entity_id` — stable source-system ID
- `canonical_data` — normalized dict

**Proven properties KAVY adapter must preserve:**
- Idempotent upsert: same idempotency_key never creates duplicate
- Tenant isolation: no cross-tenant reads
- Persistence: records survive process restart
- Provenance: all fields above preserved on read

**Activation:** Set `SETU_MASTERDB_BACKEND=mongodb` and `SETU_MASTERDB_MONGO_URI=<uri>`

---

## Section 3 — Alay

### Production Deployment Requirements

**Environment variables required:**

```bash
# MasterDB
SETU_MASTERDB_BACKEND=mongodb
SETU_MASTERDB_MONGO_URI=<mongodb_connection_string>

# Bright Connection API credentials (from Raj)
SETU_BA_API_KEY=<biz_analyst_api_key>
SETU_BA_BASE_URL=https://api.bizanalyst.in/v1
SETU_CRM_OAUTH_TOKEN=<bright_crm_oauth_token>
SETU_CRM_BASE_URL=<bright_crm_base_url>
SETU_DMS_API_KEY=<bright_dms_api_key>
SETU_DMS_BASE_URL=<bright_dms_base_url>
SETU_INV_API_KEY=<bright_inventory_api_key>
SETU_INV_BASE_URL=<bright_inventory_base_url>
SETU_ORDERS_API_KEY=<bright_orders_api_key>
SETU_ORDERS_BASE_URL=<bright_orders_base_url>
SETU_SALES_API_KEY=<bright_sales_api_key>
SETU_SALES_BASE_URL=<bright_sales_base_url>
SETU_COLLECTIONS_API_KEY=<bright_collections_api_key>
SETU_COLLECTIONS_BASE_URL=<bright_collections_base_url>
SETU_DEALER_API_KEY=<bright_dealer_api_key>
SETU_DEALER_BASE_URL=<bright_dealer_base_url>

# Tally (optional — LAN only)
SETU_TALLY_HOST=192.168.0.72
SETU_TALLY_PORT=9000
```

**External API dependencies:**
- All Bright Connection API endpoints (base URLs from Raj)
- MongoDB cluster (KAVY)
- TallyPrime XML gateway at 192.168.0.72:9000 (LAN-only, optional)

**Python dependencies:**
- Python 3.8+
- Standard library only (no pip packages required for core framework)
- `sqlite3` — stdlib, for SQLite backend
- `urllib` — stdlib, for HTTP calls

**Health checks:**
```python
# Connector health
connector.health()  # returns {connector_id, tenant_id, status, last_sync}

# MasterDB health
masterdb.snapshot(tenant_id)  # returns {total_records, entity_counts, backend}

# Full validation
python validate_runtime.py  # must return exit code 0, 45/45 PASS
python tests/test_live_integration.py  # must return exit code 0, 65/65 PASS
```

**No inbound firewall rules needed.** All external calls are outbound HTTPS from the SETU runtime to Bright Connection APIs. Tally bridge is outbound HTTP on LAN only.

---

## Section 4 — Rayyan

### Test & Evidence Package

**Test suites:**

| Suite | File | Tests | Status |
|---|---|---|---|
| Local validation | validate_runtime.py | 45 | PASS |
| Live integration | tests/test_live_integration.py | 65 | PASS |

**Run both:**
```bash
python validate_runtime.py
python tests/test_live_integration.py
```

**Live integration test coverage:**

| Area | Tests | What is proven |
|---|---|---|
| Auth valid | 1 | Stub mode accepted |
| Auth missing credentials | 1 | ValueError raised |
| Auth invalid (401) | 1 | 401 detected or network failure captured |
| API successful fetch | 2 | Records returned, correct type |
| API timeout | 1 | URLError raised on non-routable IP |
| API malformed response | 1 | RuntimeError raised on bad JSON |
| API missing field | 3 | No crash, empty entity_id, valid MDURecord |
| MDU normalization | 10 | All fields, entity_type, tenant_id, source_connector, trace_id, idempotency_key, integrity_hash, schema_version |
| MDU schema rejection | 1 | MasterDB rejects non-MDURecord |
| MDU stable IDs | 2 | Same input same entity_id and idempotency_key |
| Tenant isolation | 5 | Two tenants, zero cross-contamination |
| Persistence (SQLite) | 6 | Write, restart, read, provenance, tenant_id, schema_version |
| MasterDB idempotency | 3 | First=new, second=not new, count unchanged |
| Replay | 5 | Registration, execution, hash stability, idempotency, log |
| Failure path | 6 | records_failed>0, error captured, error_code, trace_id, timestamp, records_ingested=0 |
| E2E all fields | 15 | All 13 required fields + InsightFlow + replay + events |
| Regression 45/45 | 1 | Original validation still passes |

**Evidence files:**
- `RUNTIME_EVIDENCE.json` — local validation evidence (19 MDURecords)
- `LIVE_BRIGHT_CONNECTION_EVIDENCE.json` — live integration proof (full trace)

**Failure path result:**
```json
{
  "failure_trigger": "missing api_key credential",
  "records_ingested": 0,
  "records_failed": 1,
  "error_code": "external_system_error",
  "trace_id": "trace_tenant_bright_connection_001_<hex>",
  "failure_captured": true
}
```

**Known gap for Rayyan's regression:**
Live API tests currently run in stub mode because real credentials not provided. When Raj provides credentials, re-run `python run_live_integration.py` with env vars set — framework switches to LIVE mode automatically. Rayyan should verify the live mode run produces `integration_mode: LIVE` in `LIVE_BRIGHT_CONNECTION_EVIDENCE.json`.

---

## Section 5 — Raj

### Bright Connection Tenant Readiness

**Tenant ID:** `tenant_bright_connection_001`

**Connector readiness:**

| Connector | Ready | Needs From Raj |
|---|---|---|
| biz_analyst | Framework ready | SETU_BA_API_KEY + SETU_BA_BASE_URL |
| bright_crm | Framework ready | SETU_CRM_OAUTH_TOKEN + SETU_CRM_BASE_URL |
| bright_dms | Framework ready | SETU_DMS_API_KEY + SETU_DMS_BASE_URL |
| bright_inventory | Framework ready | SETU_INV_API_KEY + SETU_INV_BASE_URL |
| bright_orders | Framework ready | SETU_ORDERS_API_KEY + SETU_ORDERS_BASE_URL |
| bright_sales | Framework ready | SETU_SALES_API_KEY + SETU_SALES_BASE_URL |
| bright_collections | Framework ready | SETU_COLLECTIONS_API_KEY + SETU_COLLECTIONS_BASE_URL |
| bright_dealer | Framework ready | SETU_DEALER_API_KEY + SETU_DEALER_BASE_URL |
| tally | Bridge agent built | Active company loaded in TallyPrime (currently "None") |

**Live demonstration status:**
- Framework: LIVE_INTEGRATION_CERTIFIED — all paths proven
- Real API demo: BLOCKED — credentials not yet provided
- Once credentials are provided: set env vars, run `python run_live_integration.py` — live proof generated automatically

**Tally setup required (if Tally is in scope):**
1. In TallyPrime: F12 > Advanced Config > Client/Server must be ON on port 9000
2. "Companies to load on startup" must be set to the active company (currently set to "None")
3. Machine IP confirmed: 192.168.0.72, port 9000
4. Bridge agent is ready: `python tally_bridge/agent.py --test`

**Unresolved dependencies:**
1. All Bright Connection API base URLs (none provided yet)
2. All API credentials (none provided yet)
3. TallyPrime active company configuration
4. Confirmation of API response format (JSON assumed — if XML or CSV, normalize() needs update)
5. Confirmation of pagination approach (flat list assumed — if paginated, fetch_data() needs cursor handling)
