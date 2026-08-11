"""
ConnectorRuntimeContract — frozen event and error envelopes.

Every connector publishes ConnectorEvent instances.
SETU runtime consumes events without knowing connector internals.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ConnectorEventType(str, Enum):
    DATA_RECEIVED = "data_received"
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    WEBHOOK_RECEIVED = "webhook_received"
    FILE_IMPORTED = "file_imported"
    RETRY_ATTEMPTED = "retry_attempted"
    CONNECTOR_DEGRADED = "connector_degraded"


class ConnectorErrorCode(str, Enum):
    AUTH_FAILED = "auth_failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SCHEMA_MISMATCH = "schema_mismatch"
    MISSING_FIELD = "missing_field"
    EXTERNAL_SYSTEM_ERROR = "external_system_error"
    NORMALIZATION_FAILED = "normalization_failed"
    CONTRACT_VIOLATION = "contract_violation"
    TENANT_MISMATCH = "tenant_mismatch"


@dataclass
class ConnectorEvent:
    """Published by connectors into the SETU event bus."""
    event_id: str
    event_type: ConnectorEventType
    connector_id: str
    tenant_id: str
    trace_id: str
    timestamp: str
    payload: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    @classmethod
    def create(
        cls,
        event_type: ConnectorEventType,
        connector_id: str,
        tenant_id: str,
        trace_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> "ConnectorEvent":
        return cls(
            event_id=f"evt_{uuid.uuid4().hex[:16]}",
            event_type=event_type,
            connector_id=connector_id,
            tenant_id=tenant_id,
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=payload or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "connector_id": self.connector_id,
            "tenant_id": self.tenant_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "schema_version": self.schema_version,
        }


@dataclass
class ConnectorError:
    """Structured error published when a connector fails."""
    error_id: str
    error_code: ConnectorErrorCode
    connector_id: str
    tenant_id: str
    trace_id: str
    message: str
    timestamp: str
    retryable: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    attempt: int = 1

    @classmethod
    def create(
        cls,
        error_code: ConnectorErrorCode,
        connector_id: str,
        tenant_id: str,
        trace_id: str,
        message: str,
        retryable: bool = True,
        details: Optional[Dict[str, Any]] = None,
        attempt: int = 1,
    ) -> "ConnectorError":
        return cls(
            error_id=f"err_{uuid.uuid4().hex[:16]}",
            error_code=error_code,
            connector_id=connector_id,
            tenant_id=tenant_id,
            trace_id=trace_id,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            retryable=retryable,
            details=details or {},
            attempt=attempt,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "error_code": self.error_code.value,
            "connector_id": self.connector_id,
            "tenant_id": self.tenant_id,
            "trace_id": self.trace_id,
            "message": self.message,
            "timestamp": self.timestamp,
            "retryable": self.retryable,
            "details": self.details,
            "attempt": self.attempt,
        }


@dataclass
class ConnectorRuntimeContract:
    """
    Frozen runtime contract for a connector instance.
    Registered at connector boot. Immutable during runtime.
    """
    connector_id: str
    tenant_id: str
    category: str
    version: str
    auth_scheme: str
    supported_entity_types: List[str]
    retry_policy: Dict[str, Any]
    contract_hash: str = ""

    def __post_init__(self):
        if not self.contract_hash:
            self.contract_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        raw = f"{self.connector_id}|{self.tenant_id}|{self.version}|{self.category}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "tenant_id": self.tenant_id,
            "category": self.category,
            "version": self.version,
            "auth_scheme": self.auth_scheme,
            "supported_entity_types": self.supported_entity_types,
            "retry_policy": self.retry_policy,
            "contract_hash": self.contract_hash,
        }
