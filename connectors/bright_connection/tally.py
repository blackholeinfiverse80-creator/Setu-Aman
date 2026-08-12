"""
Tally Connector — TallyPrime 6.1
Connects to TallyPrime via its XML/HTTP gateway (port 9000, LAN-local).
Sends TDL XML requests, parses XML responses, normalizes into MDURecord.

Confirmed setup (Bright Connection):
  - TallyPrime 6.1 Silver
  - Tally Gateway Server: SERVER:9999 (internet)
  - Client/Server with ODBC: port 9000 (LAN)
  - Machine IP: 192.168.0.72
  - Data path: D:\\TallyPrime-Live Data\\Live Data (shared)

Connection approach: SETU Tally Bridge Agent runs on the same LAN,
polls port 9000 via HTTP XML, forwards MDURecords to SETU over HTTPS.

No business logic — field mapping only.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from connector_sdk.base_connector import BaseConnector, ConnectorCategory, ConnectorManifest
from connector_sdk.mdu_schema import MDUEntityType, MDURecord


# TDL XML request templates for TallyPrime 6.1
_TALLY_PING_XML = """<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>List of Companies</REPORTNAME>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""

_LEDGER_REQUEST_XML = """<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>List of Ledgers</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""

_VOUCHER_REQUEST_XML = """<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Day Book</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
          <SVFROMDATE>{from_date}</SVFROMDATE>
          <SVTODATE>{to_date}</SVTODATE>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""

_OUTSTANDING_REQUEST_XML = """<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Outstandings Payables</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""


class TallyConnector(BaseConnector):
    _connector_id = "tally"

    @property
    def manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            connector_id="tally",
            connector_name="TallyPrime 6.1",
            category=ConnectorCategory.ACCOUNTING,
            version="2.0",
            description=(
                "Connects to TallyPrime 6.1 via XML/HTTP gateway on port 9000 (LAN). "
                "Requires SETU Tally Bridge Agent running on the same LAN as TallyPrime. "
                "Supports ledger, voucher, invoice, and outstanding data."
            ),
            supported_entity_types=[
                MDUEntityType.LEDGER.value,
                MDUEntityType.INVOICE.value,
                MDUEntityType.JOURNAL.value,
                MDUEntityType.OUTSTANDING.value,
                MDUEntityType.PAYMENT.value,
            ],
            auth_scheme="none",          # TallyPrime XML gateway has no auth by default
            supports_polling=True,
            supports_webhook=False,
            retry_policy={
                "max_attempts": 3,
                "backoff_seconds": [2, 10, 30],
                "retryable_errors": ["timeout", "connection_refused", "server_error"],
            },
        )

    # ── Internal helpers ──────────────────────────────────────

    def _gateway_url(self) -> str:
        host = self._config.get("tally_host", "192.168.0.72")
        port = self._config.get("tally_port", 9000)
        return f"http://{host}:{port}"

    def _post_xml(self, xml_body: str) -> str:
        """
        POST XML to TallyPrime gateway and return raw response text.
        Uses urllib (stdlib) so no extra dependencies needed on the bridge agent.
        In production the bridge agent calls this; in test mode returns stub XML.
        """
        if self._config.get("test_mode", True):
            return self._stub_response(xml_body)

        import urllib.request
        import urllib.error

        url = self._gateway_url()
        data = xml_body.encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "text/xml; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._config.get("timeout_seconds", 30)) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Tally gateway unreachable at {url}: {e}")

    def _stub_response(self, xml_body: str) -> str:
        """Return realistic stub XML matching TallyPrime 6.1 response format."""
        if "List of Ledgers" in xml_body:
            return """<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <LEDGER NAME="Sunrise Distributors">
          <PARENT>Sundry Debtors</PARENT>
          <OPENINGBALANCE>10000.00</OPENINGBALANCE>
          <CLOSINGBALANCE>35000.00</CLOSINGBALANCE>
          <CURRENCYNAME>INR</CURRENCYNAME>
        </LEDGER>
        <LEDGER NAME="Apex Retailers">
          <PARENT>Sundry Debtors</PARENT>
          <OPENINGBALANCE>5000.00</OPENINGBALANCE>
          <CLOSINGBALANCE>18500.00</CLOSINGBALANCE>
          <CURRENCYNAME>INR</CURRENCYNAME>
        </LEDGER>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""
        if "Day Book" in xml_body:
            return """<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <VOUCHER VCHTYPE="Sales" DATE="20250115">
          <VOUCHERNUMBER>TV-2025-001</VOUCHERNUMBER>
          <PARTYLEDGERNAME>Sunrise Distributors</PARTYLEDGERNAME>
          <AMOUNT>45000.00</AMOUNT>
          <NARRATION>Sales invoice Jan 2025</NARRATION>
        </VOUCHER>
        <VOUCHER VCHTYPE="Receipt" DATE="20250120">
          <VOUCHERNUMBER>TV-2025-002</VOUCHERNUMBER>
          <PARTYLEDGERNAME>Sunrise Distributors</PARTYLEDGERNAME>
          <AMOUNT>20000.00</AMOUNT>
          <NARRATION>Payment received</NARRATION>
        </VOUCHER>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""
        if "Outstandings" in xml_body:
            return """<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <LEDGER NAME="Sunrise Distributors">
          <CLOSINGBALANCE>25000.00</CLOSINGBALANCE>
          <DUEDATE>20250217</DUEDATE>
        </LEDGER>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""
        # Ping / companies list
        return """<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <COMPANY NAME="Bright Connection Pvt Ltd">
          <STARTINGFROM>20240401</STARTINGFROM>
          <ENDINGAT>20250331</ENDINGAT>
        </COMPANY>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""

    # ── BaseConnector implementation ──────────────────────────

    async def authenticate(self) -> bool:
        """
        Ping TallyPrime gateway with a lightweight company list request.
        TallyPrime XML gateway has no auth — connectivity check is sufficient.
        """
        try:
            response_xml = self._post_xml(_TALLY_PING_XML)
            root = ET.fromstring(response_xml)
            # Any valid XML envelope from Tally confirms the gateway is alive
            if root.tag == "ENVELOPE":
                return True
            raise ConnectionError("Unexpected response from Tally gateway")
        except ET.ParseError as e:
            raise ConnectionError(f"Tally gateway returned invalid XML: {e}")

    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch raw records from TallyPrime XML gateway.
        Parses XML response into list of dicts for normalize().
        """
        params = params or {}

        if entity_type == MDUEntityType.LEDGER.value:
            xml = _LEDGER_REQUEST_XML
            response = self._post_xml(xml)
            return self._parse_ledgers(response)

        elif entity_type in (MDUEntityType.INVOICE.value, MDUEntityType.JOURNAL.value, MDUEntityType.PAYMENT.value):
            from_date = params.get("from_date", "20250101")
            to_date = params.get("to_date", datetime.now(timezone.utc).strftime("%Y%m%d"))
            xml = _VOUCHER_REQUEST_XML.format(from_date=from_date, to_date=to_date)
            response = self._post_xml(xml)
            return self._parse_vouchers(response, entity_type)

        elif entity_type == MDUEntityType.OUTSTANDING.value:
            xml = _OUTSTANDING_REQUEST_XML
            response = self._post_xml(xml)
            return self._parse_outstandings(response)

        return []

    # ── XML parsers ───────────────────────────────────────────

    def _parse_ledgers(self, xml_text: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        records = []
        for ledger in root.iter("LEDGER"):
            records.append({
                "tally_ledger_name": ledger.get("NAME", ""),
                "group": ledger.findtext("PARENT", ""),
                "opening_balance": self._parse_amount(ledger.findtext("OPENINGBALANCE", "0")),
                "closing_balance": self._parse_amount(ledger.findtext("CLOSINGBALANCE", "0")),
                "currency": ledger.findtext("CURRENCYNAME", "INR"),
            })
        return records

    def _parse_vouchers(self, xml_text: str, entity_type: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        records = []
        type_filter = {
            MDUEntityType.INVOICE.value: "Sales",
            MDUEntityType.PAYMENT.value: "Receipt",
            MDUEntityType.JOURNAL.value: "Journal",
        }.get(entity_type)

        for voucher in root.iter("VOUCHER"):
            vch_type = voucher.get("VCHTYPE", "")
            if type_filter and vch_type != type_filter:
                continue
            records.append({
                "tally_voucher_no": voucher.findtext("VOUCHERNUMBER", ""),
                "voucher_type": vch_type,
                "date": self._parse_tally_date(voucher.get("DATE", "")),
                "party_ledger": voucher.findtext("PARTYLEDGERNAME", ""),
                "amount": self._parse_amount(voucher.findtext("AMOUNT", "0")),
                "narration": voucher.findtext("NARRATION", ""),
            })
        return records

    def _parse_outstandings(self, xml_text: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        records = []
        for ledger in root.iter("LEDGER"):
            records.append({
                "tally_ledger_name": ledger.get("NAME", ""),
                "outstanding_amount": self._parse_amount(ledger.findtext("CLOSINGBALANCE", "0")),
                "due_date": self._parse_tally_date(ledger.findtext("DUEDATE", "")),
            })
        return records

    @staticmethod
    def _parse_amount(value: str) -> float:
        try:
            return abs(float(str(value).replace(",", "").strip()))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_tally_date(tally_date: str) -> str:
        """Convert TallyPrime YYYYMMDD to ISO YYYY-MM-DD."""
        d = str(tally_date).strip()
        if len(d) == 8:
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return d

    # ── Normalize ─────────────────────────────────────────────

    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> MDURecord:
        trace_id = self._config.get("trace_id", f"trace_{self.tenant_id}_tally")

        if entity_type == MDUEntityType.LEDGER.value:
            name = raw_record.get("tally_ledger_name", "")
            canonical = {
                "ledger_id": f"TALLY-LED-{name.replace(' ', '_').upper()}",
                "ledger_name": name,
                "group": raw_record.get("group"),
                "opening_balance": raw_record.get("opening_balance"),
                "closing_balance": raw_record.get("closing_balance"),
                "currency": raw_record.get("currency", "INR"),
            }
            entity_id = canonical["ledger_id"]

        elif entity_type == MDUEntityType.INVOICE.value:
            vno = raw_record.get("tally_voucher_no", "")
            canonical = {
                "invoice_id": vno,
                "voucher_type": raw_record.get("voucher_type"),
                "customer_name": raw_record.get("party_ledger"),
                "invoice_date": raw_record.get("date"),
                "total_amount": raw_record.get("amount"),
                "narration": raw_record.get("narration"),
                "currency": "INR",
            }
            entity_id = vno

        elif entity_type == MDUEntityType.PAYMENT.value:
            vno = raw_record.get("tally_voucher_no", "")
            canonical = {
                "payment_id": vno,
                "voucher_type": raw_record.get("voucher_type"),
                "party_name": raw_record.get("party_ledger"),
                "payment_date": raw_record.get("date"),
                "amount": raw_record.get("amount"),
                "narration": raw_record.get("narration"),
                "currency": "INR",
            }
            entity_id = vno

        elif entity_type == MDUEntityType.OUTSTANDING.value:
            name = raw_record.get("tally_ledger_name", "")
            canonical = {
                "outstanding_id": f"TALLY-OUT-{name.replace(' ', '_').upper()}",
                "customer_name": name,
                "outstanding_amount": raw_record.get("outstanding_amount"),
                "due_date": raw_record.get("due_date"),
                "currency": "INR",
            }
            entity_id = canonical["outstanding_id"]

        else:
            canonical = raw_record
            entity_id = raw_record.get("tally_voucher_no") or raw_record.get("tally_ledger_name", "unknown")

        return MDURecord(
            entity_type=MDUEntityType(entity_type),
            entity_id=entity_id,
            tenant_id=self.tenant_id,
            source_connector=self.manifest.connector_id,
            canonical_data=canonical,
            trace_id=trace_id,
            raw_ref=str(raw_record.get("tally_voucher_no") or raw_record.get("tally_ledger_name", "")),
        )
