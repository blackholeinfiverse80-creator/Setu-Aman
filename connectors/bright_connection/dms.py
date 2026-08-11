"""
Bright Connection DMS Connector
Normalizes dealer management data into MDURecord.
No business logic — field mapping only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord


class BrightDMSConnector(BaseConnector):
    _connector_id = "bright_dms"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="bright_dms",
            connector_name="Bright Connection DMS",
            category=ConnectorCategory.DMS,
            version="1.0",
            description="Connects to Bright Connection DMS for dealer, scheme, and product catalogue data.",
            supported_entity_types=[
                MDUEntityType.DEALER.value,
                MDUEntityType.SCHEME.value,
                MDUEntityType.PRODUCT_CATALOGUE.value,
            ],
            auth_scheme="api_key",
            supports_polling=True,
            supports_webhook=True,
        )

    async def authenticate(self) -> bool:
        if not self._config.get("api_key"):
            raise ValueError("bright_dms requires api_key in config")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        stubs = {
            MDUEntityType.DEALER.value: [
                {
                    "dms_dealer_id": "DLR-001",
                    "dealer_name": "Sunrise Distributors",
                    "dealer_type": "distributor",
                    "region": "Mumbai North",
                    "territory": "MH-01",
                    "contact_person": "Rajesh Kumar",
                    "phone": "+91-9800000001",
                    "email": "rajesh@sunrise.com",
                    "address": "123 Market Road, Mumbai",
                    "credit_limit": 500000.00,
                    "payment_terms": "30_days",
                    "active": True,
                }
            ],
            MDUEntityType.SCHEME.value: [
                {
                    "dms_scheme_id": "SCH-001",
                    "scheme_name": "Q1 Volume Bonus",
                    "scheme_type": "volume_discount",
                    "valid_from": "2025-01-01",
                    "valid_to": "2025-03-31",
                    "target_amount": 1000000.00,
                    "benefit_percent": 2.5,
                    "applicable_to": ["distributor", "retailer"],
                }
            ],
            MDUEntityType.PRODUCT_CATALOGUE.value: [
                {
                    "dms_product_id": "SKU-101",
                    "product_name": "Product Alpha 1L",
                    "category": "beverages",
                    "brand": "BrightBrand",
                    "sku": "SKU-101",
                    "mrp": 120.00,
                    "ptr": 100.00,
                    "pts": 90.00,
                    "uom": "bottle",
                    "case_size": 12,
                    "active": True,
                }
            ],
        }
        return stubs.get(entity_type, [])

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_dms")

        if entity_type == MDUEntityType.DEALER.value:
            canonical = {
                "dealer_id": raw_record.get("dms_dealer_id"),
                "dealer_name": raw_record.get("dealer_name"),
                "dealer_type": raw_record.get("dealer_type"),
                "region": raw_record.get("region"),
                "territory": raw_record.get("territory"),
                "contact_person": raw_record.get("contact_person"),
                "phone": raw_record.get("phone"),
                "email": raw_record.get("email"),
                "address": raw_record.get("address"),
                "credit_limit": raw_record.get("credit_limit"),
                "payment_terms": raw_record.get("payment_terms"),
                "active": raw_record.get("active", True),
            }
            entity_id = raw_record.get("dms_dealer_id", "")

        elif entity_type == MDUEntityType.SCHEME.value:
            canonical = {
                "scheme_id": raw_record.get("dms_scheme_id"),
                "scheme_name": raw_record.get("scheme_name"),
                "scheme_type": raw_record.get("scheme_type"),
                "valid_from": raw_record.get("valid_from"),
                "valid_to": raw_record.get("valid_to"),
                "target_amount": raw_record.get("target_amount"),
                "benefit_percent": raw_record.get("benefit_percent"),
                "applicable_to": raw_record.get("applicable_to", []),
            }
            entity_id = raw_record.get("dms_scheme_id", "")

        elif entity_type == MDUEntityType.PRODUCT_CATALOGUE.value:
            canonical = {
                "product_id": raw_record.get("dms_product_id"),
                "product_name": raw_record.get("product_name"),
                "category": raw_record.get("category"),
                "brand": raw_record.get("brand"),
                "sku": raw_record.get("sku"),
                "mrp": raw_record.get("mrp"),
                "ptr": raw_record.get("ptr"),
                "pts": raw_record.get("pts"),
                "uom": raw_record.get("uom"),
                "case_size": raw_record.get("case_size"),
                "active": raw_record.get("active", True),
            }
            entity_id = raw_record.get("dms_product_id", "")

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
