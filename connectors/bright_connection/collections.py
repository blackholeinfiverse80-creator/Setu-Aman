"""
Bright Connection Collections Connector
Normalizes payment collections and outstanding data into MDURecord.
No business logic — field mapping only.

Real API: HTTP GET {base_url}/collections|outstanding with X-API-Key header.
Fallback: stub data when SETU_COLLECTIONS_API_KEY not set.
"""
from __future__ import annotations

import urllib.error
import urllib.request
import json as _json
from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord
from connectors.bright_connection.auth import is_stub_mode


class BrightCollectionsConnector(BaseConnector):
    _connector_id = "bright_collections"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="bright_collections",
            connector_name="Bright Connection Collections",
            category=ConnectorCategory.ACCOUNTING,
            version="1.0",
            description="Connects to Bright Connection for payment collections and outstanding balances.",
            supported_entity_types=[
                MDUEntityType.COLLECTION.value,
                MDUEntityType.OUTSTANDING.value,
                MDUEntityType.PAYMENT.value,
            ],
            auth_scheme="api_key",
            supports_polling=True,
            supports_webhook=True,
        )

    async def authenticate(self) -> bool:
        if not self._config.get("api_key"):
            raise ValueError("bright_collections requires api_key — set SETU_COLLECTIONS_API_KEY")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not is_stub_mode(self._config) and self._config.get("base_url"):
            return self._fetch_real(entity_type, params or {})
        stubs = {
            MDUEntityType.COLLECTION.value: [
                {
                    "collection_id": "COL-2025-001",
                    "dealer_code": "DLR-001",
                    "salesperson_id": "SP-101",
                    "amount": 20000.00,
                    "collection_date": "2025-01-20",
                    "payment_mode": "cheque",
                    "reference": "CHQ-9921",
                    "invoice_id": "INV-2025-001",
                    "visit_id": "VIS-001",
                }
            ],
            MDUEntityType.OUTSTANDING.value: [
                {
                    "outstanding_id": "OUT-2025-001",
                    "dealer_code": "DLR-001",
                    "invoice_id": "INV-2025-001",
                    "outstanding_amount": 22750.00,
                    "due_date": "2025-02-17",
                    "overdue_days": 0,
                    "aging_bucket": "current",
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
            raise RuntimeError(f"bright_collections API error {e.code}: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"bright_collections fetch failed: {e}")

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_col")

        if entity_type == MDUEntityType.COLLECTION.value:
            canonical = {
                "collection_id": raw_record.get("collection_id"),
                "dealer_code": raw_record.get("dealer_code"),
                "salesperson_id": raw_record.get("salesperson_id"),
                "amount": raw_record.get("amount"),
                "collection_date": raw_record.get("collection_date"),
                "payment_mode": raw_record.get("payment_mode"),
                "reference_number": raw_record.get("reference"),
                "invoice_id": raw_record.get("invoice_id"),
                "visit_id": raw_record.get("visit_id"),
                "currency": "INR",
            }
            entity_id = raw_record.get("collection_id", "")

        elif entity_type == MDUEntityType.OUTSTANDING.value:
            canonical = {
                "outstanding_id": raw_record.get("outstanding_id"),
                "dealer_code": raw_record.get("dealer_code"),
                "invoice_id": raw_record.get("invoice_id"),
                "outstanding_amount": raw_record.get("outstanding_amount"),
                "due_date": raw_record.get("due_date"),
                "overdue_days": raw_record.get("overdue_days", 0),
                "aging_bucket": raw_record.get("aging_bucket"),
                "currency": "INR",
            }
            entity_id = raw_record.get("outstanding_id", "")

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
