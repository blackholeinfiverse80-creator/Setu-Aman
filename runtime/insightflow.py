"""
InsightFlow — SETU capability dispatcher.

Consumes MDURecord from MasterDB.
Routes records to registered capability handlers by entity_type.
No connector-specific logic — all data arrives as canonical MDURecord.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from connector_sdk.mdu_schema import MDUEntityType, MDURecord


CapabilityHandler = Callable[[MDURecord], None]


class InsightFlow:
    """
    Routes canonical MDURecords to SETU capability handlers.
    Capabilities register handlers by entity_type.
    """

    def __init__(self):
        self._handlers: Dict[str, List[CapabilityHandler]] = {}
        self._dispatch_log: List[Dict[str, Any]] = []

    def register_handler(self, entity_type: MDUEntityType, handler: CapabilityHandler) -> None:
        key = entity_type.value
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)

    def dispatch(self, record: MDURecord) -> int:
        """
        Dispatch record to all registered handlers for its entity_type.
        Returns count of handlers invoked.
        """
        handlers = self._handlers.get(record.entity_type.value, [])
        for handler in handlers:
            handler(record)

        self._dispatch_log.append({
            "entity_type": record.entity_type.value,
            "entity_id": record.entity_id,
            "tenant_id": record.tenant_id,
            "trace_id": record.trace_id,
            "handlers_invoked": len(handlers),
            "idempotency_key": record.idempotency_key,
        })
        return len(handlers)

    def get_dispatch_log(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if tenant_id:
            return [e for e in self._dispatch_log if e["tenant_id"] == tenant_id]
        return self._dispatch_log
