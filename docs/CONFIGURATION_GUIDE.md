# SETU Connector Framework — Configuration Guide

## Onboarding a New Customer

Onboarding requires zero source-code modification. The complete flow:

```
1. Create Tenant Config JSON
2. Register Connectors (one-time, already done for standard connectors)
3. Call TenantLoader.load(config_path)
4. Run ConnectorPipeline
5. Go Live
```

---

## Step 1 — Create Tenant Config

Create a file at `config/{tenant_id}.json`:

```json
{
  "tenant_id": "tenant_acme_001",
  "tenant_name": "Acme Corp",
  "tenant_type": "enterprise",
  "onboarded_at": "2025-06-01T00:00:00Z",
  "schema_version": "1.0",

  "modules": [
    "dealer_management",
    "order_management",
    "inventory_management",
    "collections",
    "field_operations",
    "insightflow"
  ],

  "roles": ["admin", "sales_manager", "salesperson", "viewer"],

  "policies": [
    "multi_tenant_isolation",
    "role_based_access",
    "data_retention_90_days",
    "audit_logging_enabled"
  ],

  "connectors": [
    {
      "connector_id": "bright_orders",
      "enabled": true,
      "auth": {
        "api_key": "<acme_orders_api_key>"
      },
      "sync_schedule": "*/15 * * * *",
      "entity_types": ["order", "invoice", "payment_receipt"]
    }
  ]
}
```

---

## Step 2 — Load Tenant (No Code Changes)

```python
from config.tenant_loader import TenantLoader
from connector_sdk.registry import ConnectorRegistry

# Connectors are already registered at startup
# (done once in application bootstrap)

tenant = TenantLoader.load("config/tenant_acme_001.json")
# Returns: {tenant_id, tenant_name, modules, roles, policies, connectors: {id: instance}}
```

---

## Step 3 — Run Pipeline

```python
from runtime.pipeline import ConnectorPipeline
from runtime.masterdb import MasterDB
from runtime.insightflow import InsightFlow
from runtime.replay import ReplayEngine

masterdb = MasterDB()
insightflow = InsightFlow()
replay = ReplayEngine()
pipeline = ConnectorPipeline(masterdb, insightflow, replay)

for connector_id, connector in tenant["connectors"].items():
    entity_types = connector._config.get("entity_types", [])
    result = await pipeline.run(connector, entity_types)
    print(f"{connector_id}: {result.records_ingested} records ingested")
```

---

## Connector Config Reference

Each connector entry in the tenant config:

```json
{
  "connector_id": "string",          // Must match a registered connector
  "enabled": true,                   // Set false to disable without removing
  "auth": { ... },                   // Auth credentials (scheme-specific)
  "sync_schedule": "cron expression",// When to sync
  "entity_types": ["string"],        // Which entity types to sync
  "note": "optional comment"         // Human-readable note (e.g. for disabled connectors)
}
```

---

## Disabling a Connector

Set `"enabled": false` — the connector contract remains defined but the instance is not created:

```json
{
  "connector_id": "tally",
  "enabled": false,
  "note": "Tally not yet available — activate when gateway is live"
}
```

---

## Adding a New Connector Type

1. Create connector class extending `BaseConnector` in `connectors/`
2. Set `_connector_id` class attribute
3. Implement `manifest`, `authenticate`, `fetch_data`, `normalize`
4. Register once at startup: `ConnectorRegistry.register(MyConnector)`
5. Add to tenant config JSON with auth and entity_types

No changes to SETU runtime, MasterDB, InsightFlow, or ReplayEngine.

---

## Tenant Config Validation Checklist

Before going live, verify:

- [ ] `tenant_id` is unique across all tenants
- [ ] All `connector_id` values match registered connectors
- [ ] All `auth` keys are present for enabled connectors
- [ ] `entity_types` lists only values supported by the connector's manifest
- [ ] `modules` match available SETU capability modules
- [ ] `roles` are defined in the SETU role registry
- [ ] `policies` are defined in the SETU policy registry

---

## Multi-Tenant Operation

Multiple tenants run simultaneously with full isolation:

```python
# Each tenant gets its own connector instances
tenant_a = TenantLoader.load("config/tenant_bright_connection_001.json")
tenant_b = TenantLoader.load("config/tenant_acme_001.json")

# Pipeline enforces tenant_id isolation — records cannot cross tenant boundaries
result_a = await pipeline.run(tenant_a["connectors"]["bright_orders"], ["order"])
result_b = await pipeline.run(tenant_b["connectors"]["bright_orders"], ["order"])

# MasterDB is partitioned by tenant_id
records_a = masterdb.list_by_type("tenant_bright_connection_001", MDUEntityType.ORDER)
records_b = masterdb.list_by_type("tenant_acme_001", MDUEntityType.ORDER)
# records_a and records_b are completely isolated
```
