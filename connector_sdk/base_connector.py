"""
BaseConnector — canonical interface every SETU connector must implement.

Rules:
- No connector may contain business logic.
- All connectors must publish data through MDURecord contracts.
- Connectors are independently replaceable without touching SETU core.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional


class ConnectorCategory(str, Enum):
    ERP = "erp"
    CRM = "crm"
    DMS = "dms"
    HRMS = "hrms"
    ACCOUNTING = "accounting"
    INVENTORY = "inventory"
    LOGISTICS = "logistics"
    GPS = "gps"
    IOT = "iot"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    REST_API = "rest_api"
    WEBHOOK = "webhook"
    FILE_IMPORT = "file_import"
    CUSTOM = "custom"


class ConnectorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DEGRADED = "degraded"
    PENDING = "pending"


@dataclass
class ConnectorManifest:
    """Static descriptor for a connector — registered once, reused across tenants."""
    connector_id: str
    connector_name: str
    category: ConnectorCategory
    version: str
    description: str
    supported_entity_types: List[str]
    auth_scheme: str                    # api_key | oauth2 | basic | none | custom
    supports_webhook: bool = False
    supports_polling: bool = True
    supports_file_import: bool = False
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {
        "max_attempts": 3,
        "backoff_seconds": [1, 5, 15],
        "retryable_errors": ["timeout", "rate_limit", "server_error"]
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "category": self.category.value,
            "version": self.version,
            "description": self.description,
            "supported_entity_types": self.supported_entity_types,
            "auth_scheme": self.auth_scheme,
            "supports_webhook": self.supports_webhook,
            "supports_polling": self.supports_polling,
            "supports_file_import": self.supports_file_import,
            "retry_policy": self.retry_policy,
        }


class BaseConnector(ABC):
    """
    Abstract base for all SETU connectors.

    Lifecycle:
        authenticate() → fetch_data() → normalize() → publish()

    Invariants:
        - normalize() MUST return MDURecord instances only.
        - No business logic inside any connector.
        - tenant_id is immutable per connector instance.
    """

    def __init__(self, tenant_id: str, config: Dict[str, Any]):
        self.tenant_id = tenant_id
        self._config = config
        self._status = ConnectorStatus.PENDING
        self._last_sync: Optional[str] = None

    @property
    @abstractmethod
    def manifest(self) -> ConnectorManifest:
        """Return the static connector manifest."""

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the external system.
        Returns True on success, raises ConnectorAuthError on failure.
        """

    @abstractmethod
    async def fetch_data(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch raw records from the external system.
        Returns raw dicts — normalization happens in normalize().
        """

    @abstractmethod
    def normalize(self, raw_record: Dict[str, Any], entity_type: str) -> "MDURecord":
        """
        Map a raw external record to a canonical MDURecord.
        MUST NOT contain business logic — only field mapping.
        """

    async def sync(self, entity_type: str, params: Optional[Dict[str, Any]] = None) -> List["MDURecord"]:
        """
        Full sync cycle: authenticate → fetch → normalize.
        Returns list of MDURecords ready for MasterDB ingestion.
        """
        await self.authenticate()
        raw_records = await self.fetch_data(entity_type, params)
        mdu_records = [self.normalize(r, entity_type) for r in raw_records]
        self._last_sync = datetime.now(timezone.utc).isoformat()
        self._status = ConnectorStatus.ACTIVE
        return mdu_records

    def health(self) -> Dict[str, Any]:
        return {
            "connector_id": self.manifest.connector_id,
            "tenant_id": self.tenant_id,
            "status": self._status.value,
            "last_sync": self._last_sync,
        }

    @staticmethod
    def make_idempotency_key(*parts: str) -> str:
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
