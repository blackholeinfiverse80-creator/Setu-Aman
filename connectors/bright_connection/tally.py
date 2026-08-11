"""
Tally Connector
Connects to Tally (XML/HTTP gateway) and normalizes accounting data into MDURecord.
Tally may be unavailable — connector contract is defined regardless.
No business logic — field mapping only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord


class TallyConnector(BaseConnector):
    _connector_id = "tally"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="tally",
            connector_name="Tally ERP",
            category=ConnectorCategory.ACCOUNTING,
            version="1.0",
            description="Connects to Tally via XML gateway for ledger, journal, and invoice data.",
            supported_entity_types=[
                MDUEntityType.LEDGER.value,
                MDUEntityType.JOURNAL.value,
                MDUEntityType.INVOICE.value,
                MDUEntityType.PAYMENT.value,
                MDUEntityType.OUTSTANDING.value,
            ],
            auth_scheme="basic",
            supports_polling=True,
            supports_webhook=False,
        )

    async def authenticate(self) -> bool:
        host = self._config.get("tally_host", "localhost")
        port = self._config.get("tally_port", 9000)
        # In production: send XML ping to Tally gateway
        # If Tally is unavailable, raise ConnectorUnavailableError — contract still defined
        if not self._config.get("enabled", True):
            raise ConnectionError("Tally connector is disabled in config — contract defined, system unavailable")
        return True

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch from Tally XML gateway.
        Stub returns contract-shaped records for validation.
        """
        stubs = {
            MDUEntityType.LEDGER.value: [
                {
                    "tally_ledger_id": "TL-001",
                    "ledger_name": "Sunrise Distributors",
                    "group": "Sundry Debtors",
                    "opening_balance": 10000.00,
                    "closing_balance": 35000.00,
                    "currency": "INR",
                }
            ],
            MDUEntityType.INVOICE.value: [
                {
                    "tally_voucher_no": "TV-2025-001",
                    "voucher_type": "Sales",
                    "party_ledger": "Sunrise Distributors",
                    "date": "2025-01-15",
                    "amount": 45000.00,
                    "narration": "Sales invoice",
                }
            ],
        }
        return stubs.get(entity_type, [])

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_tally")

        if entity_type == MDUEntityType.LEDGER.value:
            canonical = {
                "ledger_id": raw_record.get("tally_ledger_id"),
                "ledger_name": raw_record.get("ledger_name"),
                "group": raw_record.get("group"),
                "opening_balance": raw_record.get("opening_balance"),
                "closing_balance": raw_record.get("closing_balance"),
                "currency": raw_record.get("currency", "INR"),
            }
            entity_id = raw_record.get("tally_ledger_id", "")

        elif entity_type == MDUEntityType.INVOICE.value:
            canonical = {
                "invoice_id": raw_record.get("tally_voucher_no"),
                "voucher_type": raw_record.get("voucher_type"),
                "customer_name": raw_record.get("party_ledger"),
                "invoice_date": raw_record.get("date"),
                "total_amount": raw_record.get("amount"),
                "narration": raw_record.get("narration"),
                "currency": "INR",
            }
            entity_id = raw_record.get("tally_voucher_no", "")

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
