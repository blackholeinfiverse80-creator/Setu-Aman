"""
ReplayEngine — deterministic replay of canonical MDURecords.

Replay is idempotency-safe: replaying the same key produces identical output.
Tenant-isolated: replay is scoped to tenant_id.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connector_sdk.mdu_schema import MDURecord


class ReplayEngine:
    """
    Stores MDURecords by idempotency_key for deterministic replay.
    """

    def __init__(self):
        # {tenant_id: {idempotency_key: MDURecord}}
        self._store: Dict[str, Dict[str, MDURecord]] = {}
        self._replay_log: List[Dict[str, Any]] = []

    def register(self, record: MDURecord) -> None:
        if record.tenant_id not in self._store:
            self._store[record.tenant_id] = {}
        self._store[record.tenant_id][record.idempotency_key] = record

    def replay(self, tenant_id: str, idempotency_key: str) -> Optional[MDURecord]:
        """Replay a single record by idempotency_key."""
        record = self._store.get(tenant_id, {}).get(idempotency_key)
        if record:
            self._replay_log.append({
                "replayed_at": datetime.now(timezone.utc).isoformat(),
                "tenant_id": tenant_id,
                "idempotency_key": idempotency_key,
                "entity_type": record.entity_type.value,
                "entity_id": record.entity_id,
                "integrity_hash": record.integrity_hash(),
            })
        return record

    def replay_all(self, tenant_id: str) -> List[MDURecord]:
        """Replay all records for a tenant."""
        records = list(self._store.get(tenant_id, {}).values())
        for record in records:
            self.replay(tenant_id, record.idempotency_key)
        return records

    def replay_log(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if tenant_id:
            return [e for e in self._replay_log if e["tenant_id"] == tenant_id]
        return self._replay_log

    def count(self, tenant_id: str) -> int:
        return len(self._store.get(tenant_id, {}))
