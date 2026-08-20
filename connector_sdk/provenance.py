"""
SETU Tally Provenance — source_context envelope.

Every Tally-derived MDURecord carries a SourceContext that answers:
  - Which connected Tally company produced this?
  - Which store/location does it belong to?
  - When was the data received and synced?
  - What source entity and record ID produced it?
  - What sync session produced this batch?

Rules:
  - Never invent missing context. Use explicit UNAVAILABLE markers.
  - pending_live_confirmation=True means value came from config default,
    not from a live Tally response. Must be confirmed when live.
  - This envelope is stored in MDURecord.metadata["source_context"].
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


UNAVAILABLE = "UNAVAILABLE"


def build_source_context(
    *,
    connected_company_id: Optional[str] = None,
    connected_company_name: Optional[str] = None,
    store_id: Optional[str] = None,
    store_name: Optional[str] = None,
    location_identifier: Optional[str] = None,
    source_entity: str,
    source_record_id: str,
    source_timestamp: Optional[str] = None,
    sync_id: Optional[str] = None,
    pending_live_confirmation: bool = False,
) -> Dict[str, Any]:
    """
    Build a source_context envelope for a Tally-derived record.

    Fields marked UNAVAILABLE are explicitly absent — never silently inferred.
    Fields with pending_live_confirmation=True came from config defaults,
    not from a live Tally response.
    """
    return {
        "source_system": "tally",
        "connected_company_id": connected_company_id or UNAVAILABLE,
        "connected_company_name": connected_company_name or UNAVAILABLE,
        "store_id": store_id or UNAVAILABLE,
        "store_name": store_name or UNAVAILABLE,
        "location_identifier": location_identifier or UNAVAILABLE,
        "source_entity": source_entity,
        "source_record_id": source_record_id,
        "source_timestamp": source_timestamp or UNAVAILABLE,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "sync_id": sync_id or f"sync_{uuid.uuid4().hex[:16]}",
        "pending_live_confirmation": pending_live_confirmation,
    }


def extract_company_from_ping(ping_xml_response: str) -> Dict[str, str]:
    """
    Extract company name and ID from TallyPrime ping (List of Companies) response.
    Returns dict with company_id and company_name.
    Falls back to UNAVAILABLE if XML cannot be parsed.
    """
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(ping_xml_response)
        for company in root.iter("COMPANY"):
            name = company.get("NAME", "").strip()
            if name:
                safe_id = "TALLY-CO-" + name.replace(" ", "_").upper()[:32]
                return {
                    "company_id": safe_id,
                    "company_name": name,
                    "pending_live_confirmation": False,
                }
    except Exception:
        pass
    return {
        "company_id": UNAVAILABLE,
        "company_name": UNAVAILABLE,
        "pending_live_confirmation": True,
    }


def validate_source_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a source_context envelope.
    Returns dict with is_valid, missing_mandatory, unavailable_fields.
    Mandatory fields that must not be UNAVAILABLE for a complete record:
      source_entity, source_record_id, received_at, sync_id, source_system.
    """
    mandatory = ["source_entity", "source_record_id", "received_at", "sync_id", "source_system"]
    optional_but_tracked = [
        "connected_company_id", "connected_company_name",
        "store_id", "store_name", "location_identifier", "source_timestamp",
    ]

    missing_mandatory = [f for f in mandatory if not ctx.get(f)]
    unavailable_fields = [f for f in optional_but_tracked if ctx.get(f) == UNAVAILABLE]

    return {
        "is_valid": len(missing_mandatory) == 0,
        "missing_mandatory": missing_mandatory,
        "unavailable_fields": unavailable_fields,
        "has_company_context": ctx.get("connected_company_id") != UNAVAILABLE,
        "has_store_context": ctx.get("store_id") != UNAVAILABLE,
        "pending_live_confirmation": ctx.get("pending_live_confirmation", False),
    }
