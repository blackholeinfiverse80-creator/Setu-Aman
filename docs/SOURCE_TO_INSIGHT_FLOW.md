# SOURCE_TO_INSIGHT_FLOW.md

**Author:** Aman Pal
**Sprint:** 3 — Tally Context & Provenance Integration
**Status:** COMPLETE — full chain documented and tested

---

## 1. Complete End-to-End Flow

```
[1] TallyPrime 6.1 (192.168.0.72:9000)
     Company: "Bright Connection Pvt Ltd"
     Entity:  Ledger / Invoice / Payment / Outstanding
          |
          | HTTP XML POST (TDL request)
          |
[2] TallyConnector.authenticate()
     -> pings List of Companies
     -> extracts connected_company_name, connected_company_id
     -> stores in self._company_context
          |
[3] TallyConnector.fetch_data(entity_type)
     -> posts TDL XML (ledger/voucher/outstanding request)
     -> parses XML response into raw dict list
          |
[4] TallyConnector.normalize(raw_record, entity_type)
     -> maps raw dict to canonical fields
     -> calls build_source_context() from connector_sdk/provenance.py
     -> attaches source_context envelope to MDURecord.metadata
          |
          | MDURecord with source_context:
          | {
          |   entity_type: "invoice",
          |   entity_id: "TV-2025-001",
          |   tenant_id: "tenant_bright_connection_001",
          |   source_connector: "tally",
          |   canonical_data: { invoice_id, customer_name, amount, ... },
          |   trace_id: "trace_tenant_bright_connection_001_abc123",
          |   metadata: {
          |     source_context: {
          |       source_system: "tally",
          |       connected_company_id: "TALLY-CO-BRIGHT_CONNECTION_PVT_LTD",
          |       connected_company_name: "Bright Connection Pvt Ltd",
          |       store_id: "UNAVAILABLE",        <- explicit, not invented
          |       store_name: "UNAVAILABLE",       <- explicit, not invented
          |       source_entity: "invoice",
          |       source_record_id: "TV-2025-001",
          |       source_timestamp: "2025-01-15",
          |       received_at: "2025-01-15T10:30:00Z",
          |       sync_id: "trace_tenant_bright_connection_001_abc123",
          |       pending_live_confirmation: false
          |     },
          |     source_context_validation: {
          |       is_valid: true,
          |       missing_mandatory: [],
          |       unavailable_fields: ["store_id", "store_name", "location_identifier"],
          |       has_company_context: true,
          |       has_store_context: false,
          |       pending_live_confirmation: false
          |     }
          |   }
          | }
          |
[5] ConnectorPipeline.run()
     -> asserts record.tenant_id == connector.tenant_id  (tenant isolation)
     -> MasterDB.upsert(record)                          (persistence)
     -> InsightFlow.dispatch(record)                     (capability routing)
     -> ReplayEngine.register(record)                    (replay registration)
          |
[6] MasterDB (memory/sqlite/mongodb)
     -> stored by idempotency_key, partitioned by tenant_id
     -> source_context preserved in metadata column
     -> retrievable by entity_type + tenant_id
          |
[7] InsightFlow capability dispatch
     -> routes record to registered handlers by entity_type
     -> dispatch_log records: entity_type, entity_id, tenant_id, trace_id
     -> handler receives full MDURecord including source_context
          |
[8] ReplayEngine
     -> record stored by idempotency_key, scoped to tenant_id
     -> replay returns identical record with identical source_context
     -> integrity_hash proves canonical_data unchanged
          |
[9] tally_bridge/agent.py (outbound forward)
     -> serializes MDURecord.to_dict() including metadata.source_context
     -> POSTs to SETU ingest endpoint over HTTPS
     -> source_context travels with the record to bhiv-ai-crm backend
```

---

## 2. Source Context Contract

Every Tally-derived MDURecord carries this envelope in metadata["source_context"]:

| Field | Type | Source | Unavailable If |
|---|---|---|---|
| source_system | str | hardcoded "tally" | never |
| connected_company_id | str | extracted from Tally ping XML | ping fails or stub |
| connected_company_name | str | extracted from Tally ping XML | ping fails or stub |
| store_id | str | bridge_config.json store_id | not configured |
| store_name | str | bridge_config.json store_name | not configured |
| location_identifier | str | bridge_config.json location_identifier | not configured |
| source_entity | str | entity_type parameter | never |
| source_record_id | str | entity_id (voucher_no or ledger_name) | never |
| source_timestamp | str | invoice_date / payment_date / due_date | ledger/outstanding records |
| received_at | str | datetime.now(UTC) at normalize() | never |
| sync_id | str | trace_id from pipeline | never |
| pending_live_confirmation | bool | True if company came from stub/config | False when live |

---

## 3. Traceability Chain — One Complete Example

**Scenario:** Invoice TV-2025-001 from Bright Connection Tally → Mitra insight

```
Source:          TallyPrime 6.1, company "Bright Connection Pvt Ltd"
Entity:          VOUCHER VCHTYPE="Sales" DATE="20250115"
Voucher No:      TV-2025-001
Party:           Sunrise Distributors
Amount:          45000.00 INR

  -> normalize() produces MDURecord:
     entity_type:      invoice
     entity_id:        TV-2025-001
     tenant_id:        tenant_bright_connection_001
     source_connector: tally
     canonical_data:
       invoice_id:     TV-2025-001
       customer_name:  Sunrise Distributors
       total_amount:   45000.00
       invoice_date:   2025-01-15
       currency:       INR
     source_context:
       source_system:           tally
       connected_company_id:    TALLY-CO-BRIGHT_CONNECTION_PVT_LTD
       connected_company_name:  Bright Connection Pvt Ltd
       source_entity:           invoice
       source_record_id:        TV-2025-001
       source_timestamp:        2025-01-15
       received_at:             2025-01-15T10:30:00+00:00
       sync_id:                 trace_tenant_bright_connection_001_abc123

  -> MasterDB stores record
  -> InsightFlow dispatches to invoice handler
  -> Handler generates insight: "Outstanding invoice TV-2025-001 for
     Sunrise Distributors, INR 45000, from Bright Connection Pvt Ltd"
  -> Insight carries trace_id linking back to source record
  -> Replay of idempotency_key returns identical record, identical hash
```

---

## 4. Failure Handling — Missing Context

If a record arrives with missing mandatory source context:

```
validate_source_context() returns:
  is_valid: False
  missing_mandatory: ["source_record_id"]

Pipeline behaviour:
  -> Record is NOT silently accepted with invented values
  -> source_context_validation.is_valid = False stored in metadata
  -> Record still ingested (data is not lost) but flagged
  -> Operator can query MasterDB for records where
     metadata.source_context_validation.is_valid = False
```

If store context is unavailable:
```
  store_id:   "UNAVAILABLE"   <- explicit string, not null, not invented
  store_name: "UNAVAILABLE"   <- explicit string, not null, not invented
  source_context_validation.unavailable_fields: ["store_id", "store_name"]
  source_context_validation.has_store_context: false
```

---

## 5. Account/Store Isolation Enforcement

| Isolation Level | Mechanism | Status |
|---|---|---|
| Tenant isolation | pipeline asserts record.tenant_id == connector.tenant_id | ENFORCED |
| Company isolation | source_context.connected_company_id on every record | ENFORCED (Sprint 3) |
| Store isolation | source_context.store_id on every record | ENFORCED where configured |
| Cross-tenant read | MasterDB.list_by_type() requires tenant_id param | ENFORCED |
| Cross-company mixing | source_context_validation.has_company_context check | DETECTABLE |
