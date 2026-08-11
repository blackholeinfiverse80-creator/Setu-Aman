"""
Bright Connection Sales Connector
Normalizes sales history and sales performance data into MDURecord.
No business logic — field mapping only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord


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
            raise ValueError("bright_sales requires api_key in config")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
