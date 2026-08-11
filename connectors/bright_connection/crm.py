"""
Bright Connection CRM Connector
Normalizes leads, contacts, and visit data from Bright CRM into MDURecord.
No business logic — field mapping only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord


class BrightCRMConnector(BaseConnector):
    _connector_id = "bright_crm"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="bright_crm",
            connector_name="Bright Connection CRM",
            category=ConnectorCategory.CRM,
            version="1.0",
            description="Connects to Bright Connection CRM for leads, contacts, visits, and beat plans.",
            supported_entity_types=[
                MDUEntityType.LEAD.value,
                MDUEntityType.CONTACT.value,
                MDUEntityType.VISIT.value,
                MDUEntityType.VISIT_PROOF.value,
                MDUEntityType.BEAT_PLAN.value,
                MDUEntityType.ROUTE_PLAN.value,
                MDUEntityType.SHELF_IMAGE.value,
                MDUEntityType.DISPLAY_COMPLIANCE.value,
            ],
            auth_scheme="oauth2",
            supports_polling=True,
            supports_webhook=True,
        )

    async def authenticate(self) -> bool:
        token = self._config.get("oauth_token")
        if not token:
            raise ValueError("bright_crm connector requires oauth_token in config")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        stubs = {
            MDUEntityType.VISIT.value: [
                {
                    "crm_visit_id": "VIS-001",
                    "salesperson_id": "SP-101",
                    "dealer_code": "DLR-001",
                    "visit_date": "2025-01-15",
                    "visit_time": "10:30:00",
                    "purpose": "order_collection",
                    "outcome": "order_placed",
                    "gps_lat": 19.0760,
                    "gps_lng": 72.8777,
                    "checkin_time": "10:30:00",
                    "checkout_time": "11:15:00",
                }
            ],
            MDUEntityType.BEAT_PLAN.value: [
                {
                    "crm_beat_id": "BEAT-001",
                    "beat_name": "Mumbai North Beat",
                    "salesperson_id": "SP-101",
                    "day_of_week": "Monday",
                    "dealer_codes": ["DLR-001", "DLR-002", "DLR-003"],
                    "frequency": "weekly",
                }
            ],
            MDUEntityType.ROUTE_PLAN.value: [
                {
                    "crm_route_id": "ROUTE-001",
                    "route_name": "Mumbai North Route",
                    "salesperson_id": "SP-101",
                    "plan_date": "2025-01-15",
                    "stops": ["DLR-001", "DLR-002", "DLR-003"],
                    "estimated_km": 45.5,
                }
            ],
            MDUEntityType.DISPLAY_COMPLIANCE.value: [
                {
                    "crm_compliance_id": "COMP-001",
                    "dealer_code": "DLR-001",
                    "visit_id": "VIS-001",
                    "compliance_score": 85,
                    "checked_items": ["shelf_facing", "price_tag", "pos_material"],
                    "issues": [],
                }
            ],
        }
        return stubs.get(entity_type, [])

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_crm")

        if entity_type == MDUEntityType.VISIT.value:
            canonical = {
                "visit_id": raw_record.get("crm_visit_id"),
                "salesperson_id": raw_record.get("salesperson_id"),
                "dealer_code": raw_record.get("dealer_code"),
                "visit_date": raw_record.get("visit_date"),
                "visit_time": raw_record.get("visit_time"),
                "purpose": raw_record.get("purpose"),
                "outcome": raw_record.get("outcome"),
                "location": {
                    "lat": raw_record.get("gps_lat"),
                    "lng": raw_record.get("gps_lng"),
                },
                "checkin_time": raw_record.get("checkin_time"),
                "checkout_time": raw_record.get("checkout_time"),
            }
            entity_id = raw_record.get("crm_visit_id", "")

        elif entity_type == MDUEntityType.BEAT_PLAN.value:
            canonical = {
                "beat_id": raw_record.get("crm_beat_id"),
                "beat_name": raw_record.get("beat_name"),
                "salesperson_id": raw_record.get("salesperson_id"),
                "day_of_week": raw_record.get("day_of_week"),
                "dealer_codes": raw_record.get("dealer_codes", []),
                "frequency": raw_record.get("frequency"),
            }
            entity_id = raw_record.get("crm_beat_id", "")

        elif entity_type == MDUEntityType.ROUTE_PLAN.value:
            canonical = {
                "route_id": raw_record.get("crm_route_id"),
                "route_name": raw_record.get("route_name"),
                "salesperson_id": raw_record.get("salesperson_id"),
                "plan_date": raw_record.get("plan_date"),
                "stops": raw_record.get("stops", []),
                "estimated_km": raw_record.get("estimated_km"),
            }
            entity_id = raw_record.get("crm_route_id", "")

        elif entity_type == MDUEntityType.DISPLAY_COMPLIANCE.value:
            canonical = {
                "compliance_id": raw_record.get("crm_compliance_id"),
                "dealer_code": raw_record.get("dealer_code"),
                "visit_id": raw_record.get("visit_id"),
                "compliance_score": raw_record.get("compliance_score"),
                "checked_items": raw_record.get("checked_items", []),
                "issues": raw_record.get("issues", []),
            }
            entity_id = raw_record.get("crm_compliance_id", "")

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
