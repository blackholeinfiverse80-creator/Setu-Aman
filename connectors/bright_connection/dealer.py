"""
Bright Connection Dealer Connector
Normalizes dealer master and dealer hierarchy data into MDURecord.
No business logic — field mapping only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord


class BrightDealerConnector(BaseConnector):
    _connector_id = "bright_dealer"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="bright_dealer",
            connector_name="Bright Connection Dealer",
            category=ConnectorCategory.CRM,
            version="1.0",
            description="Connects to Bright Connection dealer master for dealer profiles and hierarchy.",
            supported_entity_types=[
                MDUEntityType.DEALER.value,
                MDUEntityType.CONTACT.value,
            ],
            auth_scheme="api_key",
            supports_polling=True,
            supports_webhook=False,
        )

    async def authenticate(self) -> bool:
        if not self._config.get("api_key"):
            raise ValueError("bright_dealer requires api_key in config")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        stubs = {
            MDUEntityType.DEALER.value: [
                {
                    "dealer_id": "DLR-001",
                    "dealer_name": "Sunrise Distributors",
                    "dealer_code": "SD-001",
                    "dealer_type": "distributor",
                    "parent_dealer_id": None,
                    "region": "Mumbai North",
                    "territory": "MH-01",
                    "zone": "West",
                    "gstin": "27AABCS1429B1ZB",
                    "pan": "AABCS1429B",
                    "contact_person": "Rajesh Kumar",
                    "phone": "+91-9800000001",
                    "email": "rajesh@sunrise.com",
                    "address_line1": "123 Market Road",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "pincode": "400001",
                    "credit_limit": 500000.00,
                    "payment_terms": "30_days",
                    "active": True,
                    "onboarded_date": "2020-04-01",
                }
            ],
        }
        return stubs.get(entity_type, [])

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_dealer")

        canonical = {
            "dealer_id": raw_record.get("dealer_id"),
            "dealer_name": raw_record.get("dealer_name"),
            "dealer_code": raw_record.get("dealer_code"),
            "dealer_type": raw_record.get("dealer_type"),
            "parent_dealer_id": raw_record.get("parent_dealer_id"),
            "region": raw_record.get("region"),
            "territory": raw_record.get("territory"),
            "zone": raw_record.get("zone"),
            "gstin": raw_record.get("gstin"),
            "pan": raw_record.get("pan"),
            "contact_person": raw_record.get("contact_person"),
            "phone": raw_record.get("phone"),
            "email": raw_record.get("email"),
            "address": {
                "line1": raw_record.get("address_line1"),
                "city": raw_record.get("city"),
                "state": raw_record.get("state"),
                "pincode": raw_record.get("pincode"),
            },
            "credit_limit": raw_record.get("credit_limit"),
            "payment_terms": raw_record.get("payment_terms"),
            "active": raw_record.get("active", True),
            "onboarded_date": raw_record.get("onboarded_date"),
        }
        entity_id = raw_record.get("dealer_id", "")

        return MDURecord(
            entity_type=MDUEntityType(entity_type),
            entity_id=entity_id,
            tenant_id=self.tenant_id,
            source_connector=self.manifest.connector_id,
            canonical_data=canonical,
            trace_id=trace_id,
            raw_ref=entity_id,
        )
