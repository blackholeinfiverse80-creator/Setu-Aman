"""
Biz Analyst Connector
Connects to Biz Analyst API and normalizes sales/financial data into MDURecord.
No business logic — field mapping only.

Real API: HTTP GET {base_url}/{entity_type} with X-API-Key header.
Fallback: stub data when SETU_BA_API_KEY not set (test/validation mode).
"""
from __future__ import annotations

import urllib.error
import urllib.request
import json as _json
from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord
from connectors.bright_connection.auth import is_stub_mode


class BizAnalystConnector(BaseConnector):
    _connector_id = "biz_analyst"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="biz_analyst",
            connector_name="Biz Analyst",
            category=ConnectorCategory.ACCOUNTING,
            version="1.0",
            description="Connects to Biz Analyst for sales, collections, and financial data.",
            supported_entity_types=[
                MDUEntityType.ORDER.value,
                MDUEntityType.COLLECTION.value,
                MDUEntityType.PAYMENT.value,
                MDUEntityType.OUTSTANDING.value,
                MDUEntityType.PRODUCT.value,
                MDUEntityType.CUSTOMER.value,
            ],
            auth_scheme="api_key",
            supports_polling=True,
            supports_webhook=False,
        )

    async def authenticate(self) -> bool:
        api_key = self._config.get("api_key")
        base_url = self._config.get("base_url")
        if not api_key or not base_url:
            raise ValueError("biz_analyst requires api_key and base_url — set SETU_BA_API_KEY and SETU_BA_BASE_URL")
        if is_stub_mode(self._config):
            return True  # stub mode — no real auth call
        # Real auth: validate key with a lightweight ping
        try:
            req = urllib.request.Request(
                f"{base_url}/ping",
                headers={"X-API-Key": api_key, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10):
                pass
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ValueError(f"biz_analyst auth failed: 401 Unauthorized")
            # Non-auth HTTP errors are not auth failures
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch raw records from Biz Analyst API.
        Real: HTTP GET {base_url}/{entity_type} with X-API-Key header.
        Stub: returns contract-shaped sample records when credentials absent.
        """
        params = params or {}
        if not is_stub_mode(self._config):
            return self._fetch_real(entity_type, params)
        stubs = {
            MDUEntityType.ORDER.value: [
                {
                    "ba_order_id": "BA-ORD-001",
                    "party_name": "Sunrise Distributors",
                    "party_code": "SD-001",
                    "order_date": "2025-01-15",
                    "total_amount": 45000.00,
                    "status": "confirmed",
                    "items": [{"sku": "SKU-101", "qty": 10, "rate": 4500.00}],
                }
            ],
            MDUEntityType.COLLECTION.value: [
                {
                    "ba_collection_id": "BA-COL-001",
                    "party_code": "SD-001",
                    "amount": 20000.00,
                    "collection_date": "2025-01-20",
                    "mode": "cheque",
                    "reference": "CHQ-9921",
                }
            ],
            MDUEntityType.OUTSTANDING.value: [
                {
                    "ba_outstanding_id": "BA-OUT-001",
                    "party_code": "SD-001",
                    "outstanding_amount": 25000.00,
                    "due_date": "2025-02-15",
                    "overdue_days": 0,
                }
            ],
        }
        return stubs.get(entity_type, [])

    def _fetch_real(self, entity_type: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Real HTTP fetch from Biz Analyst API."""
        base_url = self._config["base_url"].rstrip("/")
        api_key = self._config["api_key"]
        url = f"{base_url}/{entity_type}"
        req = urllib.request.Request(
            url,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return _json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"biz_analyst API error {e.code} for {entity_type}: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"biz_analyst fetch failed for {entity_type}: {e}")

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        """Map Biz Analyst raw record to canonical MDURecord. Field mapping only."""
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_ba")

        if entity_type == MDUEntityType.ORDER.value:
            canonical = {
                "order_id": raw_record.get("ba_order_id"),
                "customer_code": raw_record.get("party_code"),
                "customer_name": raw_record.get("party_name"),
                "order_date": raw_record.get("order_date"),
                "total_amount": raw_record.get("total_amount"),
                "status": raw_record.get("status"),
                "line_items": raw_record.get("items", []),
                "currency": "INR",
            }
            entity_id = raw_record.get("ba_order_id", "")

        elif entity_type == MDUEntityType.COLLECTION.value:
            canonical = {
                "collection_id": raw_record.get("ba_collection_id"),
                "customer_code": raw_record.get("party_code"),
                "amount": raw_record.get("amount"),
                "collection_date": raw_record.get("collection_date"),
                "payment_mode": raw_record.get("mode"),
                "reference_number": raw_record.get("reference"),
                "currency": "INR",
            }
            entity_id = raw_record.get("ba_collection_id", "")

        elif entity_type == MDUEntityType.OUTSTANDING.value:
            canonical = {
                "outstanding_id": raw_record.get("ba_outstanding_id"),
                "customer_code": raw_record.get("party_code"),
                "outstanding_amount": raw_record.get("outstanding_amount"),
                "due_date": raw_record.get("due_date"),
                "overdue_days": raw_record.get("overdue_days", 0),
                "currency": "INR",
            }
            entity_id = raw_record.get("ba_outstanding_id", "")

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
            raw_ref=str(raw_record.get("ba_order_id") or raw_record.get("ba_collection_id") or ""),
        )
