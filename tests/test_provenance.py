"""
SETU Provenance & Source Context Test Suite
Sprint 3 - Tally Context & Provenance Integration

Test Groups:
  A. Source context structure (6 tests)
  B. Company extraction from Tally ping (5 tests)
  C. Store/location context (4 tests)
  D. Context validation (5 tests)
  E. Company separation / tenant isolation (5 tests)
  F. End-to-end provenance chain (5 tests)

Total: 30 tests
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from connector_sdk.provenance import (
    build_source_context,
    extract_company_from_ping,
    validate_source_context,
    UNAVAILABLE,
)
from connector_sdk.mdu_schema import MDUEntityType, MDURecord
from connectors.bright_connection.tally import TallyConnector
from runtime.masterdb import MasterDB
from runtime.insightflow import InsightFlow
from runtime.replay import ReplayEngine
from runtime.pipeline import ConnectorPipeline

TENANT_A = "tenant_bright_connection_001"
TENANT_B = "tenant_other_company_002"

_pass = 0
_fail = 0


def check(name, passed, detail=""):
    global _pass, _fail
    status = "PASS" if passed else "FAIL"
    if passed:
        _pass += 1
    else:
        _fail += 1
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))
    return passed


# ── Group A: Source context structure ─────────────────────────────────────────

def test_source_context_structure():
    ctx = build_source_context(
        connected_company_id="TALLY-CO-TEST",
        connected_company_name="Test Company",
        store_id="STORE-001",
        store_name="Main Store",
        location_identifier="LOC-001",
        source_entity="invoice",
        source_record_id="TV-001",
        source_timestamp="2025-01-15",
        sync_id="sync_abc123",
    )
    check("SourceContext - source_system is tally", ctx["source_system"] == "tally")
    check("SourceContext - connected_company_id present", ctx["connected_company_id"] == "TALLY-CO-TEST")
    check("SourceContext - connected_company_name present", ctx["connected_company_name"] == "Test Company")
    check("SourceContext - store_id present", ctx["store_id"] == "STORE-001")
    check("SourceContext - source_entity present", ctx["source_entity"] == "invoice")
    check("SourceContext - received_at is UTC ISO", "T" in ctx["received_at"] and "+00:00" in ctx["received_at"])


# ── Group B: Company extraction from Tally ping ───────────────────────────────

def test_company_extraction():
    good_xml = """<ENVELOPE>
  <BODY><DATA><COLLECTION>
    <COMPANY NAME="Bright Connection Pvt Ltd">
      <STARTINGFROM>20240401</STARTINGFROM>
    </COMPANY>
  </COLLECTION></DATA></BODY>
</ENVELOPE>"""

    result = extract_company_from_ping(good_xml)
    check("CompanyExtract - name extracted correctly",
          result["company_name"] == "Bright Connection Pvt Ltd",
          result["company_name"])
    check("CompanyExtract - company_id derived from name",
          result["company_id"].startswith("TALLY-CO-"),
          result["company_id"])
    check("CompanyExtract - pending_live_confirmation is False",
          result["pending_live_confirmation"] is False)

    bad_xml = "<ENVELOPE><BODY></BODY></ENVELOPE>"
    result_bad = extract_company_from_ping(bad_xml)
    check("CompanyExtract - bad XML returns UNAVAILABLE",
          result_bad["company_id"] == UNAVAILABLE)
    check("CompanyExtract - bad XML sets pending_live_confirmation True",
          result_bad["pending_live_confirmation"] is True)


# ── Group C: Store/location context ───────────────────────────────────────────

def test_store_context():
    ctx_with_store = build_source_context(
        connected_company_id="TALLY-CO-TEST",
        connected_company_name="Test Co",
        store_id="STORE-001",
        store_name="Main Store",
        source_entity="ledger",
        source_record_id="LED-001",
    )
    check("StoreContext - store_id preserved", ctx_with_store["store_id"] == "STORE-001")
    check("StoreContext - store_name preserved", ctx_with_store["store_name"] == "Main Store")

    ctx_no_store = build_source_context(
        source_entity="ledger",
        source_record_id="LED-001",
    )
    check("StoreContext - missing store_id is UNAVAILABLE not null",
          ctx_no_store["store_id"] == UNAVAILABLE,
          ctx_no_store["store_id"])
    check("StoreContext - missing store_name is UNAVAILABLE not null",
          ctx_no_store["store_name"] == UNAVAILABLE,
          ctx_no_store["store_name"])


# ── Group D: Context validation ───────────────────────────────────────────────

def test_context_validation():
    full_ctx = build_source_context(
        connected_company_id="TALLY-CO-TEST",
        connected_company_name="Test Co",
        store_id="STORE-001",
        store_name="Main Store",
        source_entity="invoice",
        source_record_id="TV-001",
        source_timestamp="2025-01-15",
        sync_id="sync_001",
    )
    v = validate_source_context(full_ctx)
    check("Validation - full context is valid", v["is_valid"] is True)
    check("Validation - full context has company context", v["has_company_context"] is True)
    check("Validation - full context has store context", v["has_store_context"] is True)

    partial_ctx = build_source_context(
        source_entity="ledger",
        source_record_id="LED-001",
    )
    v2 = validate_source_context(partial_ctx)
    check("Validation - partial context is still valid (mandatory fields present)",
          v2["is_valid"] is True)
    check("Validation - unavailable_fields listed explicitly",
          "store_id" in v2["unavailable_fields"] and "store_name" in v2["unavailable_fields"],
          str(v2["unavailable_fields"]))


# ── Group E: Company separation / tenant isolation ────────────────────────────

async def test_company_separation():
    # Two connectors, two tenants, two companies
    # Inject company context directly (simulates what authenticate() does after
    # receiving different ping responses from two different Tally instances)
    conn_a = TallyConnector(TENANT_A, {"test_mode": True})
    conn_b = TallyConnector(TENANT_B, {"test_mode": True})

    conn_a._company_context = {
        "company_id": "TALLY-CO-COMPANY_ALPHA_LTD",
        "company_name": "Company Alpha Ltd",
        "pending_live_confirmation": False,
    }
    conn_b._company_context = {
        "company_id": "TALLY-CO-COMPANY_BETA_PVT_LTD",
        "company_name": "Company Beta Pvt Ltd",
        "pending_live_confirmation": False,
    }

    records_a = await conn_a.sync("ledger")
    records_b = await conn_b.sync("ledger")

    ctx_a = records_a[0].metadata["source_context"]
    ctx_b = records_b[0].metadata["source_context"]

    check("CompanySeparation - Company A records have Company A name",
          ctx_a["connected_company_name"] == "Company Alpha Ltd",
          ctx_a["connected_company_name"])
    check("CompanySeparation - Company B records have Company B name",
          ctx_b["connected_company_name"] == "Company Beta Pvt Ltd",
          ctx_b["connected_company_name"])
    check("CompanySeparation - Company A and B names are different",
          ctx_a["connected_company_name"] != ctx_b["connected_company_name"])
    check("CompanySeparation - Company A tenant_id is TENANT_A",
          records_a[0].tenant_id == TENANT_A)
    check("CompanySeparation - Company B tenant_id is TENANT_B",
          records_b[0].tenant_id == TENANT_B)


# ── Group F: End-to-end provenance chain ──────────────────────────────────────

async def test_e2e_provenance_chain():
    masterdb = MasterDB(backend="memory")
    insightflow = InsightFlow()
    replay = ReplayEngine()
    pipeline = ConnectorPipeline(masterdb, insightflow, replay)

    dispatched = []
    insightflow.register_handler(MDUEntityType.INVOICE, lambda r: dispatched.append(r))

    conn = TallyConnector(TENANT_A, {"test_mode": True})
    await conn.authenticate()  # extracts company context from stub ping
    result = await pipeline.run(conn, ["invoice"])

    records = masterdb.list_by_type(TENANT_A, MDUEntityType.INVOICE)
    r = records[0]

    check("E2E Provenance - source_context in metadata",
          "source_context" in r.metadata)
    check("E2E Provenance - source_system is tally",
          r.metadata["source_context"]["source_system"] == "tally")
    check("E2E Provenance - company name extracted from ping",
          r.metadata["source_context"]["connected_company_name"] != UNAVAILABLE,
          r.metadata["source_context"]["connected_company_name"])
    check("E2E Provenance - source_context survives InsightFlow dispatch",
          len(dispatched) > 0 and "source_context" in dispatched[0].metadata)

    # Replay must return identical source_context
    idem_key = result.replay_keys[0] if result.replay_keys else r.idempotency_key
    replayed = replay.replay(TENANT_A, idem_key)
    check("E2E Provenance - source_context identical after replay",
          replayed is not None and
          replayed.metadata["source_context"]["connected_company_name"] ==
          r.metadata["source_context"]["connected_company_name"])


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "=" * 65)
    print("SETU PROVENANCE & SOURCE CONTEXT TEST SUITE")
    print("Sprint 3 - Tally Context & Provenance Integration")
    print("=" * 65)

    print("\n[Group A] Source Context Structure")
    test_source_context_structure()

    print("\n[Group B] Company Extraction from Tally Ping")
    test_company_extraction()

    print("\n[Group C] Store/Location Context")
    test_store_context()

    print("\n[Group D] Context Validation")
    test_context_validation()

    print("\n[Group E] Company Separation / Tenant Isolation")
    await test_company_separation()

    print("\n[Group F] End-to-End Provenance Chain")
    await test_e2e_provenance_chain()

    print("\n" + "=" * 65)
    total = _pass + _fail
    print(f"RESULT: {_pass}/{total} tests passed, {_fail} failed")
    print(f"STATUS: {'ALL PASS' if _fail == 0 else 'FAILURES PRESENT'}")
    print("=" * 65)

    return _fail == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
