# SETU Connector Framework — Configuration Guide
**Updated:** Sprint 2 — Live Integration

---

## Quick Start

```
# 1. Run local validation (45/45)
python validate_runtime.py

# 2. Run live integration tests (65/65)
python tests/test_live_integration.py

# 3. Run live proof runner (generates LIVE_BRIGHT_CONNECTION_EVIDENCE.json)
python run_live_integration.py

# 4. When real credentials are available — set env vars and re-run
set SETU_ORDERS_API_KEY=<real_key>
set SETU_ORDERS_BASE_URL=<real_url>
python run_live_integration.py
```

---

## Credential Injection (Environment Variables)

Credentials are NEVER committed to Git. NEVER appear in MDURecord. NEVER appear in evidence.
They are injected via environment variables only.

| Connector | Env Variable | Required |
|---|---|---|
| biz_analyst | SETU_BA_API_KEY | Yes |
| biz_analyst | SETU_BA_BASE_URL | Yes (default: https://api.bizanalyst.in/v1) |
| bright_crm | SETU_CRM_OAUTH_TOKEN | Yes |
| bright_crm | SETU_CRM_BASE_URL | Yes |
| bright_dms | SETU_DMS_API_KEY | Yes |
| bright_dms | SETU_DMS_BASE_URL | Yes |
| bright_inventory | SETU_INV_API_KEY | Yes |
| bright_inventory | SETU_INV_BASE_URL | Yes |
| bright_orders | SETU_ORDERS_API_KEY | Yes |
| bright_orders | SETU_ORDERS_BASE_URL | Yes |
| bright_sales | SETU_SALES_API_KEY | Yes |
| bright_sales | SETU_SALES_BASE_URL | Yes |
| bright_collections | SETU_COLLECTIONS_API_KEY | Yes |
| bright_collections | SETU_COLLECTIONS_BASE_URL | Yes |
| bright_dealer | SETU_DEALER_API_KEY | Yes |
| bright_dealer | SETU_DEALER_BASE_URL | Yes |
| tally | SETU_TALLY_HOST | Optional (default: 192.168.0.72) |
| tally | SETU_TALLY_PORT | Optional (default: 9000) |

If env vars are absent, connectors run in stub mode automatically. Stub mode is explicitly flagged.

---

## MasterDB Backend Selection

```
set SETU_MASTERDB_BACKEND=memory    # default — in-memory, used by validate_runtime.py
set SETU_MASTERDB_BACKEND=sqlite    # file-backed, proves persistence across restart
set SETU_MASTERDB_BACKEND=mongodb   # production — requires KAVY adapter + SETU_MASTERDB_MONGO_URI
```

SQLite file location (default: `data/masterdb.sqlite`):
```
set SETU_MASTERDB_SQLITE_PATH=C:\path\to\masterdb.sqlite
```

MongoDB URI (production):
```
set SETU_MASTERDB_MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>/setu_masterdb
```

---

## Onboarding a New Customer

Zero source-code modification required:

```
1. Create config/{tenant_id}.json
2. Register connectors (one-time at startup)
3. Call TenantLoader.load(config_path)
4. Run ConnectorPipeline
```

### Tenant Config Template

```json
{
  "tenant_id": "tenant_acme_001",
  "tenant_name": "Acme Corp",
  "tenant_type": "enterprise",
  "onboarded_at": "2025-06-01T00:00:00Z",
  "schema_version": "1.0",
  "modules": ["dealer_management", "order_management", "insightflow"],
  "roles": ["admin", "sales_manager", "salesperson", "viewer"],
  "policies": ["multi_tenant_isolation", "role_based_access", "audit_logging_enabled"],
  "connectors": [
    {
      "connector_id": "bright_orders",
      "enabled": true,
      "auth": {"api_key": "<acme_orders_api_key>"},
      "sync_schedule": "*/15 * * * *",
      "entity_types": ["order", "invoice", "payment_receipt"]
    }
  ]
}
```

### Load and Run

```python
from config.tenant_loader import TenantLoader
from runtime.pipeline import ConnectorPipeline
from runtime.masterdb import MasterDB
from runtime.insightflow import InsightFlow
from runtime.replay import ReplayEngine

tenant = TenantLoader.load("config/tenant_acme_001.json")
masterdb = MasterDB()  # backend from SETU_MASTERDB_BACKEND env var
pipeline = ConnectorPipeline(masterdb, InsightFlow(), ReplayEngine())

for connector_id, connector in tenant["connectors"].items():
    entity_types = connector._config.get("entity_types", [])
    result = await pipeline.run(connector, entity_types)
    print(f"{connector_id}: {result.records_ingested} records ingested")
```

---

## Disabling a Connector

```json
{
  "connector_id": "tally",
  "enabled": false,
  "note": "Tally not yet available — activate when gateway is live"
}
```

---

## Adding a New Connector

1. Create connector class in `connectors/` extending `BaseConnector`
2. Set `_connector_id` class attribute
3. Implement `manifest`, `authenticate`, `fetch_data`, `normalize`
4. Add env var mapping to `connectors/bright_connection/auth.py`
5. Register once: `ConnectorRegistry.register(MyConnector)`
6. Add to tenant config JSON

No changes to SETU runtime, MasterDB, InsightFlow, or ReplayEngine.

---

## Multi-Tenant Operation

```python
# Each tenant gets isolated connector instances and MasterDB partitions
tenant_a = TenantLoader.load("config/tenant_bright_connection_001.json")
tenant_b = TenantLoader.load("config/tenant_acme_001.json")

# Pipeline enforces tenant_id — records cannot cross tenant boundaries
result_a = await pipeline.run(tenant_a["connectors"]["bright_orders"], ["order"])
result_b = await pipeline.run(tenant_b["connectors"]["bright_orders"], ["order"])

# MasterDB partitioned by tenant_id
records_a = masterdb.list_by_type("tenant_bright_connection_001", MDUEntityType.ORDER)
records_b = masterdb.list_by_type("tenant_acme_001", MDUEntityType.ORDER)
# records_a and records_b are completely isolated — proven by test suite
```

---

## Stub vs Live Mode

| Condition | Mode | Behaviour |
|---|---|---|
| Env vars absent | STUB | Connector returns contract-shaped sample data |
| Env vars present, base_url set | LIVE | Connector makes real HTTP calls to external API |
| API returns 401 | LIVE FAIL | RuntimeError raised, captured by pipeline as ConnectorError |
| API times out | LIVE FAIL | RuntimeError raised, captured by pipeline as ConnectorError |

Stub mode is explicitly flagged in connector config as `_stub_mode: True`.
Stub data is contract-shaped — same field structure as real API responses.
Switching from stub to live requires only setting env vars — zero code changes.

---

## Tenant Config Validation Checklist

- [ ] `tenant_id` is unique across all tenants
- [ ] All `connector_id` values match registered connectors
- [ ] All `auth` keys present for enabled connectors (or env vars set)
- [ ] `entity_types` only contains values in connector's manifest
- [ ] `modules` match available SETU capability modules
- [ ] `roles` defined in SETU role registry
- [ ] `policies` defined in SETU policy registry
- [ ] No credentials hardcoded — use env vars or `<placeholder>` in config
