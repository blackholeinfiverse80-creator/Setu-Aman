# CURRENT_RUNTIME_MAPPING.md

**Author:** Aman Pal
**Date:** Sprint 3 — Tally Context & Provenance Integration
**Status:** Phase 1 Complete — Pre-change audit

---

## 1. Current Ingestion Path

```
TallyPrime 6.1 (192.168.0.72:9000)
    |
    | HTTP XML POST (TDL requests)
    v
tally_bridge/agent.py          -- LAN-local bridge process
    |
    | calls connector.sync(entity_type)
    v
connectors/bright_connection/tally.py  -- TallyConnector
    |  authenticate()  -> pings /List of Companies
    |  fetch_data()    -> posts TDL XML, parses response
    |  normalize()     -> maps raw dict to MDURecord
    v
MDURecord (canonical schema)
    |
    v
runtime/pipeline.py            -- ConnectorPipeline.run()
    |  upsert -> MasterDB
    |  dispatch -> InsightFlow
    |  register -> ReplayEngine
    v
runtime/masterdb.py            -- MasterDB (memory/sqlite/mongodb)
runtime/insightflow.py         -- InsightFlow capability dispatch
runtime/replay.py              -- ReplayEngine deterministic replay
```

---

## 2. Existing Context Fields (Before This Sprint)

Fields present on every MDURecord before Sprint 3:

| Field | Present | Notes |
|---|---|---|
| entity_type | YES | e.g. ledger, invoice, payment, outstanding |
| entity_id | YES | derived from tally_ledger_name or tally_voucher_no |
| tenant_id | YES | tenant_bright_connection_001 |
| source_connector | YES | "tally" |
| canonical_data | YES | normalized fields (ledger_name, amount, date etc.) |
| trace_id | YES | set by pipeline per sync run |
| ingested_at | YES | UTC ISO timestamp of MDURecord creation |
| idempotency_key | YES | SHA-256 of tenant+entity_type+entity_id+connector |
| integrity_hash | YES | SHA-256 of canonical_data |
| raw_ref | YES | opaque pointer to tally_voucher_no or tally_ledger_name |
| schema_version | YES | "1.0" |
| metadata | YES | empty dict {} — no provenance content |

---

## 3. Missing Provenance Fields (Before This Sprint)

Fields required by the task contract that did NOT exist before Sprint 3:

| Field | Status Before | Impact |
|---|---|---|
| source_context.source_system | MISSING | Cannot identify data came from Tally |
| source_context.connected_company_id | MISSING | Cannot attribute record to a Tally company |
| source_context.connected_company_name | MISSING | Company identity invisible |
| source_context.store_id | MISSING | Store/location context absent |
| source_context.store_name | MISSING | Store/location context absent |
| source_context.location_identifier | MISSING | Location context absent |
| source_context.source_entity | MISSING | Entity type not in provenance envelope |
| source_context.source_record_id | MISSING | Source record ID not in provenance envelope |
| source_context.source_timestamp | MISSING | Source-side timestamp absent |
| source_context.received_at | MISSING | Receive timestamp absent from envelope |
| source_context.sync_id | MISSING | Sync session not tracked in record |
| source_context_validation | MISSING | No validation of context completeness |

---

## 4. Existing Account/Store Isolation Behaviour

Before Sprint 3:

- Tenant isolation: ENFORCED. Pipeline asserts record.tenant_id == connector.tenant_id. Cross-tenant writes rejected.
- Company isolation: NOT ENFORCED at record level. All Tally records for a tenant share the same tenant_id but carry no company-level identifier.
- Store isolation: NOT PRESENT. No store_id or store_name field anywhere in the pipeline.
- MasterDB: Partitioned by tenant_id only. No company or store partition.

---

## 5. Files Changed in This Sprint

| File | Change |
|---|---|
| connector_sdk/provenance.py | NEW — source_context envelope builder, company extractor, validator |
| connectors/bright_connection/tally.py | UPGRADED — authenticate() extracts company context; normalize() attaches source_context to metadata |
| tests/test_provenance.py | NEW — 30 provenance/context/isolation tests |
| docs/CURRENT_RUNTIME_MAPPING.md | NEW — this file |
| docs/SOURCE_TO_INSIGHT_FLOW.md | NEW — end-to-end flow documentation |
| docs/HANDOVER.md | NEW — full handover package |

---

## 6. Known Limitations

1. **Company name from stub**: In test_mode=True, company name is "Bright Connection Pvt Ltd" from stub XML. Must be confirmed against live TallyPrime response.

2. **Store context from config only**: TallyPrime 6.1 Silver does not expose store/location as a structured field in standard TDL exports. Store context must be injected via connector config (store_id, store_name in bridge_config.json). If not configured, store_id = UNAVAILABLE — explicitly marked, never invented.

3. **Single company assumption**: Current bridge_config.json connects to one Tally instance. If Bright Connection runs multiple Tally companies, each needs a separate bridge agent instance with its own tenant config.

4. **source_timestamp availability**: Only available for voucher-type records (invoice_date, payment_date). Ledger and outstanding records have source_timestamp = UNAVAILABLE — this is correct and explicit.

5. **MongoDB backend**: Still a stub awaiting KAVY adapter. source_context is stored in MDURecord.metadata which persists correctly in memory and SQLite backends.
