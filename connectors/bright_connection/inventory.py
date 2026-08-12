"""
Bright Connection Inventory Connector
Normalizes stock and damaged goods data into MDURecord.
No business logic — field mapping only.

Real API: HTTP GET {base_url}/inventory|damaged_goods with X-API-Key header.
Fallback: stub data when SETU_INV_API_KEY not set.
"""
from __future__ import annotations

import urllib.error
import urllib.request
import json as _json
from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord
from connectors.bright_connection.auth import is_stub_mode


class BrightInventoryConnector(BaseConnector):
    _connector_id = "bright_inventory"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="bright_inventory",
            connector_name="Bright Connection Inventory",
            category=ConnectorCategory.INVENTORY,
            version="1.0",
            description="Connects to Bright Connection inventory system for stock levels and damaged goods.",
            supported_entity_types=[
                MDUEntityType.INVENTORY.value,
                MDUEntityType.DAMAGED_GOODS.value,
            ],
            auth_scheme="api_key",
            supports_polling=True,
            supports_webhook=True,
        )

    async def authenticate(self) -> bool:
        if not self._config.get("api_key"):
            raise ValueError("bright_inventory requires api_key — set SETU_INV_API_KEY")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not is_stub_mode(self._config) and self._config.get("base_url"):
            return self._fetch_real(entity_type, params or {})
        stubs = {
            MDUEntityType.INVENTORY.value: [
                {
                    "inv_id": "INV-001",
                    "sku": "SKU-101",
                    "warehouse_code": "WH-MUM-01",
                    "batch_no": "BATCH-2025-01",
                    "qty_available": 500,
                    "qty_reserved": 50,
                    "qty_in_transit": 100,
                    "expiry_date": "2026-01-01",
                    "last_updated": "2025-01-15T10:00:00Z",
                }
            ],
            MDUEntityType.DAMAGED_GOODS.value: [
                {
                    "damage_id": "DMG-001",
                    "sku": "SKU-101",
                    "dealer_code": "DLR-001",
                    "visit_id": "VIS-001",
                    "qty_damaged": 5,
                    "damage_reason": "transit_breakage",
                    "reported_date": "2025-01-15",
                    "image_ref": "img_dmg_001.jpg",
                }
            ],
        }
        return stubs.get(entity_type, [])

    def _fetch_real(self, entity_type: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        base_url = self._config["base_url"].rstrip("/")
        api_key = self._config["api_key"]
        req = urllib.request.Request(
            f"{base_url}/{entity_type}",
            headers={"X-API-Key": api_key, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return _json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"bright_inventory API error {e.code}: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"bright_inventory fetch failed: {e}")

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_inv")

        if entity_type == MDUEntityType.INVENTORY.value:
            canonical = {
                "inventory_id": raw_record.get("inv_id"),
                "sku": raw_record.get("sku"),
                "warehouse_code": raw_record.get("warehouse_code"),
                "batch_no": raw_record.get("batch_no"),
                "qty_available": raw_record.get("qty_available"),
                "qty_reserved": raw_record.get("qty_reserved"),
                "qty_in_transit": raw_record.get("qty_in_transit"),
                "expiry_date": raw_record.get("expiry_date"),
                "last_updated": raw_record.get("last_updated"),
            }
            entity_id = raw_record.get("inv_id", "")

        elif entity_type == MDUEntityType.DAMAGED_GOODS.value:
            canonical = {
                "damage_id": raw_record.get("damage_id"),
                "sku": raw_record.get("sku"),
                "dealer_code": raw_record.get("dealer_code"),
                "visit_id": raw_record.get("visit_id"),
                "qty_damaged": raw_record.get("qty_damaged"),
                "damage_reason": raw_record.get("damage_reason"),
                "reported_date": raw_record.get("reported_date"),
                "image_ref": raw_record.get("image_ref"),
            }
            entity_id = raw_record.get("damage_id", "")

        else:
            canonical = raw_record
            entity_id = raw_record.get("id", "unknown")

        return MDURecord(
            entity_type=MDUEntityType(entity_type),
            entity_id=entity_id,
            tenant_id=self.tenant_id,
            source_connector=self.manifest.connector_id,
            canonical_data=canonical,
            trace_id=trace_id,
            raw_ref=entity_id,
        )
