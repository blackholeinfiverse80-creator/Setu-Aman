# HANDOVER.md

**Author:** Aman Pal
**Sprint:** 3 — Tally Context & Provenance Integration
**Handover To:** Rudra (integration), KAVY (MasterDB), Alay (ops), Rayyan (QA), Raj (architecture)

---

## 1. What Existed Before This Task

Sprint 1 delivered:
- Full SETU Connector Framework inside Setu(Aman)/
- 9 Bright Connection connectors (biz_analyst, tally, crm, dms, inventory, orders, sales, collections, dealer)
- ConnectorPipeline, MasterDB (3 backends), InsightFlow, ReplayEngine
- 45/45 validate_runtime.py passing

Sprint 2 delivered:
- Real HTTP paths on all 9 connectors (stub fallback when env vars absent)
- auth.py credential boundary (env vars only, never in MDURecord)
- 65/65 live integration tests passing
- LIVE_INTEGRATION_CERTIFIED status

Before Sprint 3, every Tally-derived MDURecord had:
- tenant_id, entity_type, entity_id, source_connector, canonical_data, trace_id
- metadata = {} (empty — no provenance content)
- No company identity, no store identity, no source_context envelope

---

## 2. What Aman Changed in Sprint 3

### New File: connector_sdk/provenance.py
- build_source_context() — constructs the full source_context envelope
- extract_company_from_ping() — parses company name/ID from Tally ping XML response
- validate_source_context() — validates envelope completeness, returns explicit unavailable fields
- UNAVAILABLE constant — used instead of null/None for missing optional context

### Upgraded File: connectors/bright_connection/tally.py
- authenticate() now calls extract_company_from_ping() and stores result in self._company_context
- normalize() now calls build_source_context() and attaches envelope to MDURecord.metadata
- source_context_validation also stored in metadata alongside source_context
- No changes to fetch_data(), XML parsers, or canonical field mapping

### New File: tests/test_provenance.py
- 30 tests across 6 groups: source_context structure, company extraction, store context, validation, tenant isolation, E2E provenance chain
- All 30 pass

### New Docs:
- docs/CURRENT_RUNTIME_MAPPING.md — pre-change audit
- docs/SOURCE_TO_INSIGHT_FLOW.md — full chain documentation
- docs/HANDOVER.md — this file

---

## 3. Files Changed

| File | Type | What Changed |
|---|---|---|
| connector_sdk/provenance.py | NEW | source_context envelope module |
| connectors/bright_connection/tally.py | MODIFIED | authenticate() + normalize() |
| tests/test_provenance.py | NEW | 30 provenance tests |
| docs/CURRENT_RUNTIME_MAPPING.md | NEW | pre-change audit |
| docs/SOURCE_TO_INSIGHT_FLOW.md | NEW | E2E flow doc |
| docs/HANDOVER.md | NEW | this file |

No changes to: pipeline.py, masterdb.py, insightflow.py, replay.py, mdu_schema.py, auth.py, any other connector, validate_runtime.py, test_live_integration.py

---

## 4. Current Runtime Flow

```
TallyPrime (192.168.0.72:9000)
  -> TallyConnector.authenticate()  [extracts company context from ping]
  -> TallyConnector.fetch_data()    [TDL XML -> raw dicts]
  -> TallyConnector.normalize()     [raw dict -> MDURecord + source_context]
  -> ConnectorPipeline.run()        [tenant check -> MasterDB -> InsightFlow -> Replay]
  -> tally_bridge/agent.py          [forwards MDURecord.to_dict() to SETU endpoint]
```

---

## 5. Source-Context Contract

Every Tally MDURecord.metadata["source_context"] contains:

```json
{
  "source_system": "tally",
  "connected_company_id": "TALLY-CO-BRIGHT_CONNECTION_PVT_LTD",
  "connected_company_name": "Bright Connection Pvt Ltd",
  "store_id": "UNAVAILABLE",
  "store_name": "UNAVAILABLE",
  "location_identifier": "UNAVAILABLE",
  "source_entity": "invoice",
  "source_record_id": "TV-2025-001",
  "source_timestamp": "2025-01-15",
  "received_at": "2025-01-15T10:30:00+00:00",
  "sync_id": "trace_tenant_bright_connection_001_abc123",
  "pending_live_confirmation": false
}
```

UNAVAILABLE means the field is explicitly absent — never silently invented.
pending_live_confirmation=true means the value came from config/stub, not a live Tally response.

---

## 6. Known Limitations

1. **Store context requires config**: TallyPrime 6.1 Silver does not expose store/location in standard TDL exports. To add store context, set store_id and store_name in bridge_config.json tally section.

2. **Company name from stub in test_mode**: When test_mode=true, company name is "Bright Connection Pvt Ltd" from stub XML. Set test_mode=false and run against live Tally to get the real company name. pending_live_confirmation will become false automatically.

3. **Single Tally instance**: Current setup assumes one Tally company per bridge agent. Multiple companies need separate bridge agent instances.

4. **MongoDB backend**: Still a stub. source_context is in MDURecord.metadata which persists correctly in SQLite. MongoDB adapter from KAVY will inherit it automatically.

---

## 7. How to Run the Test/Demo Path

### Run provenance tests (30 new tests):
```
cd Setu(Aman)
python tests/test_provenance.py
```

### Run full regression (45/45 + 65/65 + 30 new = 140 total):
```
python validate_runtime.py
python tests/test_live_integration.py
python tests/test_provenance.py
```

### Run Tally bridge read test (requires LAN access to 192.168.0.72:9000):
```
python tally_bridge/agent.py --test
```
Output shows source_context on every record in read_test_evidence.json.

### Inspect a record's provenance:
```python
from runtime.masterdb import MasterDB
from connector_sdk.mdu_schema import MDUEntityType

db = MasterDB(backend="sqlite")
records = db.list_by_type("tenant_bright_connection_001", MDUEntityType.INVOICE)
for r in records:
    print(r.metadata["source_context"])
    print(r.metadata["source_context_validation"])
```

---

## 8. What an Incoming Developer Must Know

1. All work is inside Setu(Aman)/ — zero changes to bhiv-ai-crm-main/
2. source_context lives in MDURecord.metadata["source_context"] — it travels with the record through the entire pipeline
3. UNAVAILABLE is a string constant, not null — query for it explicitly when checking context completeness
4. pending_live_confirmation=True means the value needs to be verified against a live Tally instance
5. The connector_sdk/provenance.py module is the single place to change source_context structure — do not add provenance fields directly in tally.py
6. Tenant isolation is enforced by the pipeline — source_context adds company/store isolation on top of it
7. To add store context: add store_id and store_name to the tally section of bridge_config.json
8. To confirm company name: run with test_mode=false against live TallyPrime — authenticate() will extract the real name

---

## 9. Handover by Recipient

### Rudra
- Sprint 3 adds source_context to MDURecord.metadata — no pipeline changes needed
- The to_dict() output now includes metadata.source_context — this travels to bhiv-ai-crm ingest endpoint automatically
- No changes to your existing build required to receive the enriched records

### KAVY
- source_context is stored in MDURecord.metadata (dict field)
- SQLite schema already has a metadata TEXT column (JSON serialized)
- MongoDB adapter must preserve the metadata field as a nested document
- No schema migration needed for memory or SQLite backends

### Alay
- New env vars for store context (optional): none required — store context is config-file driven
- Existing env vars unchanged
- New file to run: tests/test_provenance.py

### Rayyan
- 30 new tests in tests/test_provenance.py
- All 30 pass
- Total test count: 45 + 65 + 30 = 140
- Evidence in RUNTIME_EVIDENCE.json and LIVE_BRIGHT_CONNECTION_EVIDENCE.json

### Raj
- source_context contract defined in connector_sdk/provenance.py
- Contract fields documented in SOURCE_TO_INSIGHT_FLOW.md Section 2
- UNAVAILABLE sentinel pattern used for missing optional fields
- validate_source_context() returns structured validation result for observability
