"""
SETU Tally Bridge Agent
=======================
Runs as a local process on the same LAN as TallyPrime (or on the Tally machine itself).
Polls TallyPrime XML gateway on port 9000, normalizes data into MDURecords,
and forwards them to SETU over HTTPS.

Why a bridge agent is required:
  - TallyPrime XML gateway (port 9000) is LAN-local only — not internet-accessible.
  - SETU cannot reach port 9000 directly from the cloud.
  - The bridge agent runs inside the LAN, acts as a secure outbound relay.
  - All traffic from bridge to SETU is outbound HTTPS — no inbound firewall rules needed.

Confirmed Bright Connection setup:
  - TallyPrime 6.1 Silver
  - Tally machine IP: 192.168.0.72
  - XML gateway port: 9000
  - Tally Gateway Server: SERVER:9999 (internet, for Tally's own sync — not used here)

Usage:
  python tally_bridge/agent.py --config tally_bridge/bridge_config.json

  Or for a one-shot read test:
  python tally_bridge/agent.py --test
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List

# Make SDK importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from connector_sdk.registry import ConnectorRegistry
from connector_sdk.mdu_schema import MDUEntityType
from connectors.bright_connection.tally import TallyConnector

# Register Tally connector
try:
    ConnectorRegistry.register(TallyConnector)
except Exception:
    pass  # Already registered


def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path) as f:
        return json.load(f)


def post_to_setu(setu_endpoint: str, api_key: str, records: List[Dict]) -> bool:
    """
    Forward MDURecords to SETU ingest endpoint over HTTPS.
    Outbound HTTPS only — no inbound firewall rules required.
    """
    payload = json.dumps({
        "schema_version": "1.0",
        "source": "tally_bridge_agent",
        "records": records,
        "forwarded_at": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")

    req = urllib.request.Request(
        setu_endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-SETU-API-Key": api_key,
            "X-SETU-Source": "tally_bridge",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except urllib.error.URLError as e:
        print(f"[BridgeAgent] SETU forward failed: {e}")
        return False


async def run_read_test(config: Dict[str, Any]) -> None:
    """
    One-shot read test: connect to TallyPrime, fetch ledgers and vouchers,
    print normalized MDURecords. Does not forward to SETU.
    """
    tenant_id = config.get("tenant_id", "tenant_bright_connection_001")
    tally_cfg = config.get("tally", {})
    tally_cfg["test_mode"] = tally_cfg.get("test_mode", True)

    connector = ConnectorRegistry.create_instance("tally", tenant_id, tally_cfg)

    print("\n" + "=" * 60)
    print("SETU TALLY BRIDGE AGENT — READ TEST")
    print(f"  Tally host : {tally_cfg.get('tally_host', '192.168.0.72')}")
    print(f"  Tally port : {tally_cfg.get('tally_port', 9000)}")
    print(f"  Test mode  : {tally_cfg.get('test_mode', True)}")
    print(f"  Tenant     : {tenant_id}")
    print("=" * 60)

    # Step 1: Authenticate (ping gateway)
    print("\n[1] Pinging TallyPrime XML gateway...")
    try:
        ok = await connector.authenticate()
        print(f"    Gateway reachable: {ok}")
    except ConnectionError as e:
        print(f"    FAILED: {e}")
        return

    # Step 2: Fetch and normalize each entity type
    entity_types = [
        MDUEntityType.LEDGER.value,
        MDUEntityType.INVOICE.value,
        MDUEntityType.PAYMENT.value,
        MDUEntityType.OUTSTANDING.value,
    ]

    all_records = []
    for etype in entity_types:
        print(f"\n[2] Fetching {etype}...")
        try:
            records = await connector.sync(etype)
            for r in records:
                all_records.append(r.to_dict())
                print(f"    [{r.entity_type.value}] {r.entity_id}")
                print(f"      idempotency_key : {r.idempotency_key}")
                print(f"      integrity_hash  : {r.integrity_hash()[:24]}...")
                print(f"      canonical_data  : {json.dumps(r.canonical_data, indent=6)}")
        except Exception as e:
            print(f"    ERROR fetching {etype}: {e}")

    print(f"\n[3] Total MDURecords normalized: {len(all_records)}")
    print("\n[4] Read test complete.")
    print("    To forward to SETU, run without --test flag with setu_endpoint configured.")
    print("=" * 60)

    # Write evidence
    evidence_path = os.path.join(os.path.dirname(__file__), "read_test_evidence.json")
    with open(evidence_path, "w") as f:
        json.dump({
            "test_run_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
            "tally_host": tally_cfg.get("tally_host"),
            "tally_port": tally_cfg.get("tally_port"),
            "records_normalized": len(all_records),
            "records": all_records,
        }, f, indent=2, default=str)
    print(f"\nEvidence written to: tally_bridge/read_test_evidence.json")


async def run_sync_loop(config: Dict[str, Any]) -> None:
    """
    Continuous sync loop: poll TallyPrime at configured interval,
    forward MDURecords to SETU.
    """
    tenant_id = config["tenant_id"]
    tally_cfg = config["tally"]
    setu_cfg = config["setu"]
    interval_seconds = config.get("poll_interval_seconds", 300)

    connector = ConnectorRegistry.create_instance("tally", tenant_id, tally_cfg)
    entity_types = config.get("entity_types", [MDUEntityType.LEDGER.value, MDUEntityType.INVOICE.value])

    print(f"[BridgeAgent] Starting sync loop — interval={interval_seconds}s")

    while True:
        try:
            await connector.authenticate()
            all_records = []
            for etype in entity_types:
                records = await connector.sync(etype)
                all_records.extend([r.to_dict() for r in records])

            if all_records:
                ok = post_to_setu(setu_cfg["endpoint"], setu_cfg["api_key"], all_records)
                status = "forwarded" if ok else "forward_failed"
                print(f"[BridgeAgent] {datetime.now(timezone.utc).isoformat()} "
                      f"synced {len(all_records)} records — {status}")
            else:
                print(f"[BridgeAgent] {datetime.now(timezone.utc).isoformat()} no records")

        except Exception as e:
            print(f"[BridgeAgent] ERROR: {e}")

        await asyncio.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="SETU Tally Bridge Agent")
    parser.add_argument("--config", default="tally_bridge/bridge_config.json",
                        help="Path to bridge config JSON")
    parser.add_argument("--test", action="store_true",
                        help="Run one-shot read test (no SETU forwarding)")
    args = parser.parse_args()

    config_path = args.config
    if not os.path.exists(config_path):
        # Use defaults for test mode
        config = {
            "tenant_id": "tenant_bright_connection_001",
            "tally": {
                "tally_host": "192.168.0.72",
                "tally_port": 9000,
                "test_mode": True,
                "timeout_seconds": 30,
            },
            "setu": {
                "endpoint": "https://setu.example.com/connectors/tally/ingest",
                "api_key": "<setu_api_key>",
            },
            "entity_types": ["ledger", "invoice", "payment", "outstanding"],
            "poll_interval_seconds": 300,
        }
    else:
        config = load_config(config_path)

    if args.test:
        asyncio.run(run_read_test(config))
    else:
        asyncio.run(run_sync_loop(config))


if __name__ == "__main__":
    main()
