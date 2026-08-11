"""
Bright Connection Orders Connector
Normalizes order and invoice capture data into MDURecord.
No business logic — field mapping only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord


class BrightOrdersConnector(BaseConnector):
    _connector_id = "bright_orders"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="bright_orders",
            connector_name="Bright Connection Orders",
            category=ConnectorCategory.ERP,
            version="1.0",
            description="Connects to Bright Connection order management for orders, invoices, and payment receipts.",
            supported_entity_types=[
                MDUEntityType.ORDER.value,
                MDUEntityType.ORDER_LINE.value,
                MDUEntityType.INVOICE.value,
                MDUEntityType.PAYMENT_RECEIPT.value,
            ],
            auth_scheme="api_key",
            supports_polling=True,
            supports_webhook=True,
        )

    async def authenticate(self) -> bool:
        if not self._config.get("api_key"):
            raise ValueError("bright_orders requires api_key in config")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        stubs = {
            MDUEntityType.ORDER.value: [
                {
                    "order_id": "ORD-2025-001",
                    "dealer_code": "DLR-001",
                    "salesperson_id": "SP-101",
                    "order_date": "2025-01-15",
                    "delivery_date": "2025-01-18",
                    "status": "confirmed",
                    "total_amount": 45000.00,
                    "discount_amount": 2250.00,
                    "net_amount": 42750.00,
                    "currency": "INR",
                    "visit_id": "VIS-001",
                }
            ],
            MDUEntityType.INVOICE.value: [
                {
                    "invoice_id": "INV-2025-001",
                    "order_id": "ORD-2025-001",
                    "dealer_code": "DLR-001",
                    "invoice_date": "2025-01-18",
                    "due_date": "2025-02-17",
                    "total_amount": 42750.00,
                    "status": "unpaid",
                    "image_ref": "img_inv_001.jpg",
                }
            ],
            MDUEntityType.PAYMENT_RECEIPT.value: [
                {
                    "receipt_id": "RCP-2025-001",
                    "invoice_id": "INV-2025-001",
                    "dealer_code": "DLR-001",
                    "amount": 20000.00,
                    "payment_date": "2025-01-25",
                    "payment_mode": "cheque",
                    "reference": "CHQ-9921",
                    "image_ref": "img_rcp_001.jpg",
                }
            ],
        }
        return stubs.get(entity_type, [])

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_orders")

        if entity_type == MDUEntityType.ORDER.value:
            canonical = {
                "order_id": raw_record.get("order_id"),
                "dealer_code": raw_record.get("dealer_code"),
                "salesperson_id": raw_record.get("salesperson_id"),
                "order_date": raw_record.get("order_date"),
                "delivery_date": raw_record.get("delivery_date"),
                "status": raw_record.get("status"),
                "total_amount": raw_record.get("total_amount"),
                "discount_amount": raw_record.get("discount_amount"),
                "net_amount": raw_record.get("net_amount"),
                "currency": raw_record.get("currency", "INR"),
                "visit_id": raw_record.get("visit_id"),
            }
            entity_id = raw_record.get("order_id", "")

        elif entity_type == MDUEntityType.INVOICE.value:
            canonical = {
                "invoice_id": raw_record.get("invoice_id"),
                "order_id": raw_record.get("order_id"),
                "dealer_code": raw_record.get("dealer_code"),
                "invoice_date": raw_record.get("invoice_date"),
                "due_date": raw_record.get("due_date"),
                "total_amount": raw_record.get("total_amount"),
                "status": raw_record.get("status"),
                "image_ref": raw_record.get("image_ref"),
            }
            entity_id = raw_record.get("invoice_id", "")

        elif entity_type == MDUEntityType.PAYMENT_RECEIPT.value:
            canonical = {
                "receipt_id": raw_record.get("receipt_id"),
                "invoice_id": raw_record.get("invoice_id"),
                "dealer_code": raw_record.get("dealer_code"),
                "amount": raw_record.get("amount"),
                "payment_date": raw_record.get("payment_date"),
                "payment_mode": raw_record.get("payment_mode"),
                "reference_number": raw_record.get("reference"),
                "image_ref": raw_record.get("image_ref"),
            }
            entity_id = raw_record.get("receipt_id", "")

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
