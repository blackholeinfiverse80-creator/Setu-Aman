"""
Bright Connection Sales Connector
Normalizes sales history and sales performance data into MDURecord.
No business logic — field mapping only.

Real API: HTTP GET {base_url}/order with X-API-Key header.
Fallback: stub data when SETU_SALES_API_KEY not set.
"""
from __future__ import annotations

import urllib.error
import urllib.request
import json as _json
from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord
from connectors.bright_connection.auth import is_stub_mode


class BrightSalesConnector(BaseConnector):
    _connector_id = "bright_sales"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="bright_sales",
            connector_name="Bright Connection Sales",
            category=ConnectorCategory.CRM,
            version="1.0",
            description="Connects to Bright Connection sales system for sales history and performance data.",
            supported_entity_types=[
                MDUEntityType.ORDER.value,
                MDUEntityType.CUSTOMER.value,
            ],
            auth_scheme="api_key",
            supports_polling=True,
            supports_webhook=False,
        )

    async def authenticate(self) -> bool:
        if not self._config.get("api_key"):
            raise ValueError("bright_sales requires api_key — set SETU_SALES_API_KEY")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not is_stub_mode(self._config) and self._config.get("base_url"):
            return self._fetch_real(entity_type, params or {})
        stubs = {
            MDUEntityType.ORDER.value: [
                {
                    "sales_order_id": "SO-2025-001",
                    "dealer_code": "DLR-001",
                    "salesperson_id": "SP-101",
                    "sale_date": "2025-01-15",
                    "sku": "SKU-101",
                    "qty_sold": 10,
                    "rate": 100.00,
                    "gross_amount": 1000.00,
                    "discount": 50.00,
                    "net_amount": 950.00,
                    "period": "2025-01",
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
            raise RuntimeError(f"bright_sales API error {e.code}: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"bright_sales fetch failed: {e}")

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_sales")

        canonical = {
            "order_id": raw_record.get("sales_order_id"),
            "dealer_code": raw_record.get("dealer_code"),
            "salesperson_id": raw_record.get("salesperson_id"),
            "order_date": raw_record.get("sale_date"),
            "sku": raw_record.get("sku"),
            "qty_sold": raw_record.get("qty_sold"),
            "rate": raw_record.get("rate"),
            "gross_amount": raw_record.get("gross_amount"),
            "discount_amount": raw_record.get("discount"),
            "net_amount": raw_record.get("net_amount"),
            "period": raw_record.get("period"),
            "currency": "INR",
        }
        entity_id = raw_record.get("sales_order_id", "")

        return MDURecord(
            entity_type=MDUEntityType(entity_type),
            entity_id=entity_id,
            tenant_id=self.tenant_id,
            source_connector=self.manifest.connector_id,
            canonical_data=canonical,
            trace_id=trace_id,
            raw_ref=entity_id,
        )
