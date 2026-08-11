"""
MDU (Master Data Unit) — canonical enterprise data schema.

Every connector normalizes external data into MDURecord.
No connector-specific fields leak past this boundary.
MasterDB only accepts MDURecord instances.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class MDUEntityType(str, Enum):
    # CRM / Sales
    DEALER = "dealer"
    CUSTOMER = "customer"
    CONTACT = "contact"
    LEAD = "lead"

    # Commerce
    ORDER = "order"
    ORDER_LINE = "order_line"
    INVOICE = "invoice"
    PAYMENT = "payment"
    PAYMENT_RECEIPT = "payment_receipt"
    OUTSTANDING = "outstanding"

    # Inventory / Product
    PRODUCT = "product"
    PRODUCT_CATALOGUE = "product_catalogue"
    INVENTORY = "inventory"
    SCHEME = "scheme"
    DAMAGED_GOODS = "damaged_goods"

    # Field Operations
    ROUTE_PLAN = "route_plan"
    BEAT_PLAN = "beat_plan"
    VISIT = "visit"
    VISIT_PROOF = "visit_proof"
    SHELF_IMAGE = "shelf_image"
    DISPLAY_COMPLIANCE = "display_compliance"

    # Finance / Accounting
    LEDGER = "ledger"
    JOURNAL = "journal"
    COLLECTION = "collection"

    # HR / Org
    EMPLOYEE = "employee"
    ROLE = "role"

    # Logistics
    SHIPMENT = "shipment"
    DELIVERY = "delivery"
    GPS_PING = "gps_ping"

    # Generic
    CUSTOM = "custom"


@dataclass
class MDURecord:
    """
    Canonical data unit flowing through the SETU runtime.

    Invariants:
    - entity_id is globally unique within tenant scope.
    - source_connector identifies origin without leaking connector logic.
    - canonical_data contains only normalized, schema-compliant fields.
    - raw_ref is an opaque pointer back to source — never processed by SETU.
    - trace_id and tenant_id are immutable once set.
    """
    entity_type: MDUEntityType
    entity_id: str
    tenant_id: str
    source_connector: str
    canonical_data: Dict[str, Any]
    trace_id: str
    schema_version: str = "1.0"
    raw_ref: Optional[str] = None           # opaque reference to source record
    ingested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    idempotency_key: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.idempotency_key:
            self.idempotency_key = self._compute_idempotency_key()

    def _compute_idempotency_key(self) -> str:
        raw = f"{self.tenant_id}|{self.entity_type.value}|{self.entity_id}|{self.source_connector}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def integrity_hash(self) -> str:
        payload = json.dumps(self.canonical_data, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "tenant_id": self.tenant_id,
            "source_connector": self.source_connector,
            "canonical_data": self.canonical_data,
            "trace_id": self.trace_id,
            "schema_version": self.schema_version,
            "raw_ref": self.raw_ref,
            "ingested_at": self.ingested_at,
            "idempotency_key": self.idempotency_key,
            "integrity_hash": self.integrity_hash(),
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MDURecord":
        return cls(
            entity_type=MDUEntityType(data["entity_type"]),
            entity_id=data["entity_id"],
            tenant_id=data["tenant_id"],
            source_connector=data["source_connector"],
            canonical_data=data["canonical_data"],
            trace_id=data["trace_id"],
            schema_version=data.get("schema_version", "1.0"),
            raw_ref=data.get("raw_ref"),
            ingested_at=data.get("ingested_at", datetime.now(timezone.utc).isoformat()),
            idempotency_key=data.get("idempotency_key", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
