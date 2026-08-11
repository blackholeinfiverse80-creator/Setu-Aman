# SETU Connector SDK — Documentation

## Purpose

The Connector SDK is the canonical interface layer between external enterprise systems and the SETU Enterprise Operating System. Every external system connects through a connector. No connector may contain business logic. All data flows as MDURecord.

---

## Core Contracts

### BaseConnector

Abstract base class every connector must extend.

**Required class attribute:**
- `_connector_id: str` — unique identifier, used by ConnectorRegistry

**Required implementations:**
- `manifest` → `ConnectorManifest` — static descriptor, read-only
- `authenticate()` → `bool` — validate credentials against external system
- `fetch_data(entity_type, params)` → `List[dict]` — pull raw records
- `normalize(raw_record, entity_type)` → `MDURecord` — map to canonical schema

**Provided by base:**
- `sync(entity_type, params)` — full lifecycle: authenticate → fetch → normalize
- `health()` — connector status snapshot
- `make_idempotency_key(*parts)` — deterministic key generator

**Invariants:**
- `normalize()` MUST return `MDURecord` only — no raw dicts past this boundary
- `tenant_id` is immutable per connector instance
- No business logic inside any connector method

---

### ConnectorManifest

Static descriptor registered once per connector class.

| Field | Type | Description |
|---|---|---|
| connector_id | str | Unique connector identifier |
| connector_name | str | Human-readable name |
| category | ConnectorCategory | ERP / CRM / DMS / HRMS / ACCOUNTING / INVENTORY / LOGISTICS / GPS / IOT / WHATSAPP / EMAIL / REST_API / WEBHOOK / FILE_IMPORT / CUSTOM |
| version | str | Semantic version |
| description | str | What this connector connects to |
| supported_entity_types | List[str] | MDUEntityType values this connector produces |
| auth_scheme | str | api_key / oauth2 / basic / none / custom |
| supports_webhook | bool | Whether connector can receive push events |
| supports_polling | bool | Whether connector supports pull sync |
| supports_file_import | bool | Whether connector accepts CSV/Excel |
| retry_policy | dict | max_attempts, backoff_seconds, retryable_errors |

---

### MDURecord — Canonical Data Unit

All connectors normalize external data into `MDURecord`. MasterDB only accepts `MDURecord` instances.

| Field | Type | Description |
|---|---|---|
| entity_type | MDUEntityType | Canonical entity classification |
| entity_id | str | Unique ID within tenant scope |
| tenant_id | str | Immutable tenant boundary |
| source_connector | str | Origin connector ID |
| canonical_data | dict | Normalized, schema-compliant fields |
| trace_id | str | Immutable trace for lineage |
| schema_version | str | Contract version (default "1.0") |
| raw_ref | str | Opaque pointer to source record — never processed by SETU |
| ingested_at | str | ISO-8601 ingestion timestamp |
| idempotency_key | str | SHA-256 of tenant+entity_type+entity_id+connector |
| integrity_hash | str | SHA-256 of canonical_data — computed on demand |
| tags | List[str] | Optional classification tags |
| metadata | dict | Optional pass-through metadata |

**Supported MDUEntityType values:**
dealer, customer, contact, lead, order, order_line, invoice, payment, payment_receipt, outstanding, product, product_catalogue, inventory, scheme, damaged_goods, route_plan, beat_plan, visit, visit_proof, shelf_image, display_compliance, ledger, journal, collection, employee, role, shipment, delivery, gps_ping, custom

---

### ConnectorRegistry

Central catalog. Connectors register once. Tenants bind instances via config.

```python
# Register a connector class (done once at startup)
ConnectorRegistry.register(MyConnector)

# Create a tenant-scoped instance
instance = ConnectorRegistry.create_instance("my_connector", tenant_id, config)

# List all registered connectors
ConnectorRegistry.list_all()

# List by category
ConnectorRegistry.list_by_category(ConnectorCategory.CRM)
```

---

### ConnectorRuntimeContract

Frozen contract registered at connector boot. Immutable during runtime.

**ConnectorEvent** — published by connectors into the SETU event bus:
- event_id, event_type, connector_id, tenant_id, trace_id, timestamp, payload

**ConnectorEventType values:**
data_received, sync_started, sync_completed, sync_failed, auth_success, auth_failed, webhook_received, file_imported, retry_attempted, connector_degraded

**ConnectorError** — structured error envelope:
- error_id, error_code, connector_id, tenant_id, trace_id, message, retryable, details, attempt

**ConnectorErrorCode values:**
auth_failed, timeout, rate_limited, schema_mismatch, missing_field, external_system_error, normalization_failed, contract_violation, tenant_mismatch

---

## Building a New Connector

```python
from connector_sdk import BaseConnector, ConnectorManifest, ConnectorCategory, MDURecord, MDUEntityType

class MyERPConnector(BaseConnector):
    _connector_id = "my_erp"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="my_erp",
            connector_name="My ERP System",
            category=ConnectorCategory.ERP,
            version="1.0",
            description="Connects to My ERP for orders and inventory.",
            supported_entity_types=["order", "inventory"],
            auth_scheme="api_key",
        )

    async def authenticate(self) -> bool:
        # Validate self._config["api_key"] against ERP auth endpoint
        return True

    async def fetch_data(self, entity_type, params=None):
        # HTTP call to ERP API — return raw dicts
        return [{"erp_order_id": "ERP-001", "amount": 5000}]

    def normalize(self, raw_record, entity_type):
        # Field mapping only — no business logic
        return MDURecord(
            entity_type=MDUEntityType(entity_type),
            entity_id=raw_record["erp_order_id"],
            tenant_id=self.tenant_id,
            source_connector=self.manifest.connector_id,
            canonical_data={"order_id": raw_record["erp_order_id"], "amount": raw_record["amount"]},
            trace_id=self._config.get("trace_id", ""),
        )
```

Then register and use:

```python
ConnectorRegistry.register(MyERPConnector)
instance = ConnectorRegistry.create_instance("my_erp", "tenant_xyz", {"api_key": "..."})
records = await instance.sync("order")
```

---

## Runtime Flow

```
External System
      |
  Connector.sync(entity_type)
      |
  MDURecord (canonical)
      |
  MasterDB.upsert(record)        -- idempotent, tenant-isolated
      |
  InsightFlow.dispatch(record)   -- routes to capability handlers
      |
  ReplayEngine.register(record)  -- deterministic replay by idempotency_key
```

---

## Authentication Schemes

| Scheme | Config Keys Required |
|---|---|
| api_key | api_key, base_url |
| oauth2 | oauth_token (or client_id + client_secret + token_url) |
| basic | username, password, base_url |
| none | (no auth required) |
| custom | connector-defined keys |

---

## Retry Policy

Default retry policy applied to all connectors unless overridden in manifest:

```json
{
  "max_attempts": 3,
  "backoff_seconds": [1, 5, 15],
  "retryable_errors": ["timeout", "rate_limit", "server_error"]
}
```

---

## Versioning

- `schema_version: "1.0"` is the current contract version
- Future versions must be additive and backward compatible
- Breaking changes require a new version negotiated by policy
- `connector.manifest.version` tracks the connector implementation version independently

---

## Authority Boundaries

Connectors MAY:
- Authenticate with external systems
- Fetch raw data from external systems
- Map raw fields to canonical MDURecord fields
- Raise ConnectorError on failure

Connectors MUST NOT:
- Implement business logic
- Modify MasterDB schemas
- Bypass MDU contracts
- Duplicate intelligence owned by SETU capabilities
- Introduce client-specific platform code
- Call other connectors directly
