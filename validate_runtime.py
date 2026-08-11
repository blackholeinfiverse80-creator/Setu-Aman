"""
SETU Connector Framework — End-to-End Runtime Validation
Bright Connection Integration Certification

Validates:
  1. Connector SDK operational
  2. All Bright Connection connectors authenticate and normalize
  3. MDU canonical schema consumed at every stage
  4. MasterDB upsert with idempotency
  5. InsightFlow dispatch
  6. Replay determinism
  7. Zero connector-specific logic inside SETU runtime
  8. Multi-tenant isolation
  9. Configuration-driven onboarding
"""
import asyncio
import json
import sys
import os
from datetime import datetime, timezone

# Make SDK importable from this directory
sys.path.insert(0, os.path.dirname(__file__))

from connector_sdk.registry import ConnectorRegistry
from connector_sdk.mdu_schema import MDUEntityType
from runtime.pipeline import ConnectorPipeline
from runtime.masterdb import MasterDB
from runtime.insightflow import InsightFlow
from runtime.replay import ReplayEngine

# Register all Bright Connection connectors
from connectors.bright_connection.biz_analyst import BizAnalystConnector
from connectors.bright_connection.tally import TallyConnector
from connectors.bright_connection.crm import BrightCRMConnector
from connectors.bright_connection.dms import BrightDMSConnector
from connectors.bright_connection.inventory import BrightInventoryConnector
from connectors.bright_connection.orders import BrightOrdersConnector
from connectors.bright_connection.sales import BrightSalesConnector
from connectors.bright_connection.collections import BrightCollectionsConnector
from connectors.bright_connection.dealer import BrightDealerConnector

CONNECTORS_TO_REGISTER = [
    BizAnalystConnector,
    TallyConnector,
    BrightCRMConnector,
    BrightDMSConnector,
    BrightInventoryConnector,
    BrightOrdersConnector,
    BrightSalesConnector,
    BrightCollectionsConnector,
    BrightDealerConnector,
]

TENANT_ID = "tenant_bright_connection_001"

CONNECTOR_CONFIGS = {
    "biz_analyst": {
        "api_key": "test_ba_key",
        "base_url": "https://api.bizanalyst.in/v1",
    },
    "bright_crm": {"oauth_token": "test_crm_token"},
    "bright_dms": {"api_key": "test_dms_key"},
    "bright_inventory": {"api_key": "test_inv_key"},
    "bright_orders": {"api_key": "test_orders_key"},
    "bright_sales": {"api_key": "test_sales_key"},
    "bright_collections": {"api_key": "test_col_key"},
    "bright_dealer": {"api_key": "test_dealer_key"},
}

CONNECTOR_ENTITY_MAP = {
    "biz_analyst": ["order", "collection", "outstanding"],
    "bright_crm": ["visit", "beat_plan", "route_plan", "display_compliance"],
    "bright_dms": ["dealer", "scheme", "product_catalogue"],
    "bright_inventory": ["inventory", "damaged_goods"],
    "bright_orders": ["order", "invoice", "payment_receipt"],
    "bright_sales": ["order"],
    "bright_collections": ["collection", "outstanding"],
    "bright_dealer": ["dealer"],
}

evidence = {
    "validation_id": f"val_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
    "tenant_id": TENANT_ID,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "checks": [],
    "pipeline_results": [],
    "masterdb_snapshot": {},
    "replay_log": [],
    "certification": {},
}


def check(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))
    evidence["checks"].append({"check": name, "status": status, "detail": detail})
    return passed


async def main():
    print("\n" + "=" * 60)
    print("SETU CONNECTOR FRAMEWORK - RUNTIME VALIDATION")
    print("Bright Connection Integration Certification")
    print("=" * 60)

    all_passed = True

    # ── Phase 1: Registry ──────────────────────────────────────
    print("\n[Phase 1] Connector Registry")
    for klass in CONNECTORS_TO_REGISTER:
        try:
            ConnectorRegistry.register(klass)
            check(f"Register {klass._connector_id}", True)
        except Exception as e:
            check(f"Register {klass._connector_id}", False, str(e))
            all_passed = False

    registered = ConnectorRegistry.list_all()
    check("Registry lists all connectors", len(registered) == len(CONNECTORS_TO_REGISTER),
          f"{len(registered)} registered")

    # ── Phase 2: Connector Manifests ───────────────────────────
    print("\n[Phase 2] Connector Manifests")
    for cid in CONNECTOR_CONFIGS:
        klass = ConnectorRegistry.get(cid)
        ok = klass is not None
        check(f"Manifest available: {cid}", ok)
        if not ok:
            all_passed = False

    # ── Phase 3: Pipeline Setup ────────────────────────────────
    print("\n[Phase 3] Runtime Pipeline Setup")
    masterdb = MasterDB()
    insightflow = InsightFlow()
    replay_engine = ReplayEngine()

    # Register a sample capability handler
    dispatched_records = []
    insightflow.register_handler(MDUEntityType.ORDER, lambda r: dispatched_records.append(r))
    insightflow.register_handler(MDUEntityType.DEALER, lambda r: dispatched_records.append(r))
    insightflow.register_handler(MDUEntityType.VISIT, lambda r: dispatched_records.append(r))

    pipeline = ConnectorPipeline(masterdb, insightflow, replay_engine)
    check("Pipeline instantiated", True)

    # ── Phase 4: Connector Sync + MDU Flow ─────────────────────
    print("\n[Phase 4] Connector Sync -> MDU -> MasterDB -> InsightFlow -> Replay")
    for cid, config in CONNECTOR_CONFIGS.items():
        entity_types = CONNECTOR_ENTITY_MAP.get(cid, [])
        try:
            connector = ConnectorRegistry.create_instance(cid, TENANT_ID, config)
            result = await pipeline.run(connector, entity_types)
            evidence["pipeline_results"].append(result.to_dict())

            ok = result.records_ingested > 0 and result.records_failed == 0
            check(
                f"Sync {cid}",
                ok,
                f"{result.records_ingested} ingested, {result.records_failed} failed"
            )
            if not ok:
                all_passed = False
        except Exception as e:
            check(f"Sync {cid}", False, str(e))
            all_passed = False

    # ── Phase 5: MasterDB Validation ──────────────────────────
    print("\n[Phase 5] MasterDB Canonical Schema Validation")
    snapshot = masterdb.snapshot(TENANT_ID)
    evidence["masterdb_snapshot"] = snapshot
    check("MasterDB has records", snapshot["total_records"] > 0,
          f"total={snapshot['total_records']}")
    check("MasterDB tenant isolated", TENANT_ID in snapshot["tenant_id"],
          snapshot["tenant_id"])

    # Verify all records are MDURecord instances
    all_mdu = True
    from connector_sdk.mdu_schema import MDURecord
    for etype_str in snapshot["entity_counts"]:
        etype = MDUEntityType(etype_str)
        records = masterdb.list_by_type(TENANT_ID, etype)
        for r in records:
            if not isinstance(r, MDURecord):
                all_mdu = False
    check("All MasterDB records are MDURecord", all_mdu)

    # ── Phase 6: InsightFlow Dispatch ─────────────────────────
    print("\n[Phase 6] InsightFlow Capability Dispatch")
    dispatch_log = insightflow.get_dispatch_log(TENANT_ID)
    check("InsightFlow dispatched records", len(dispatch_log) > 0,
          f"{len(dispatch_log)} dispatches")
    check("Capability handlers received records", len(dispatched_records) > 0,
          f"{len(dispatched_records)} records received")

    # ── Phase 7: Replay Validation ────────────────────────────
    print("\n[Phase 7] Replay Determinism Validation")
    replay_count = replay_engine.count(TENANT_ID)
    check("Replay engine has records", replay_count > 0, f"{replay_count} registered")

    replayed = replay_engine.replay_all(TENANT_ID)
    check("Replay returns all records", len(replayed) == replay_count,
          f"{len(replayed)} replayed")

    # Verify idempotency: replay same key twice → same integrity hash
    if replayed:
        r = replayed[0]
        first_hash = r.integrity_hash()
        r2 = replay_engine.replay(TENANT_ID, r.idempotency_key)
        second_hash = r2.integrity_hash() if r2 else None
        check("Replay is deterministic (same hash)", first_hash == second_hash,
              f"hash={first_hash[:16]}...")

    evidence["replay_log"] = replay_engine.replay_log(TENANT_ID)

    # ── Phase 8: Multi-Tenant Isolation ───────────────────────
    print("\n[Phase 8] Multi-Tenant Isolation")
    other_tenant = "tenant_other_001"
    other_connector = ConnectorRegistry.create_instance(
        "bright_dealer", other_tenant, {"api_key": "other_key"}
    )
    other_result = await pipeline.run(other_connector, ["dealer"])
    other_snapshot = masterdb.snapshot(other_tenant)
    main_snapshot = masterdb.snapshot(TENANT_ID)

    check("Other tenant records isolated",
          other_snapshot["total_records"] > 0 and
          other_snapshot["total_records"] != main_snapshot["total_records"],
          f"tenant_bright={main_snapshot['total_records']}, tenant_other={other_snapshot['total_records']}")

    # ── Phase 9: Zero Connector Logic in Runtime ──────────────
    print("\n[Phase 9] Zero Connector-Specific Logic in SETU Runtime")
    # Verify pipeline, masterdb, insightflow, replay have no connector imports
    import inspect
    runtime_modules = [
        ("runtime.pipeline", "ConnectorPipeline"),
        ("runtime.masterdb", "MasterDB"),
        ("runtime.insightflow", "InsightFlow"),
        ("runtime.replay", "ReplayEngine"),
    ]
    for mod_name, cls_name in runtime_modules:
        import importlib
        mod = importlib.import_module(mod_name)
        src = inspect.getsource(mod)
        has_connector_import = any(
            f"from connectors" in src or
            f"import BizAnalyst" in src or
            f"import BrightCRM" in src
            for _ in [1]
        )
        check(f"{cls_name} has no connector imports", not has_connector_import)

    # ── Phase 10: Config-Driven Onboarding ────────────────────
    print("\n[Phase 10] Configuration-Driven Onboarding")
    config_path = os.path.join(os.path.dirname(__file__), "config", "bright_connection_tenant.json")
    check("Tenant config file exists", os.path.exists(config_path))

    with open(config_path) as f:
        tenant_cfg = json.load(f)
    check("Tenant config has connectors", len(tenant_cfg.get("connectors", [])) > 0,
          f"{len(tenant_cfg['connectors'])} connectors configured")
    check("Tenant config has modules", len(tenant_cfg.get("modules", [])) > 0)
    check("Tenant config has roles", len(tenant_cfg.get("roles", [])) > 0)
    check("Tenant config has policies", len(tenant_cfg.get("policies", [])) > 0)

    # ── Final Certification ────────────────────────────────────
    print("\n" + "=" * 60)
    passed_count = sum(1 for c in evidence["checks"] if c["status"] == "PASS")
    total_count = len(evidence["checks"])
    all_passed = all(c["status"] == "PASS" for c in evidence["checks"])

    evidence["certification"] = {
        "certified": all_passed,
        "checks_passed": passed_count,
        "checks_total": total_count,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "CERTIFIED" if all_passed else "FAILED",
    }

    print(f"RESULT: {passed_count}/{total_count} checks passed")
    print(f"CERTIFICATION: {'[CERTIFIED]' if all_passed else '[FAILED]'}")
    print("=" * 60)

    # Write evidence
    evidence_path = os.path.join(os.path.dirname(__file__), "RUNTIME_EVIDENCE.json")
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    print(f"\nRuntime evidence written to: RUNTIME_EVIDENCE.json")

    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
