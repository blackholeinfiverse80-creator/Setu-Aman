"""
MasterDB — canonical enterprise data store.

Accepts only MDURecord instances.
Enforces idempotency via idempotency_key.
Tenant-isolated: no cross-tenant reads.
In production: backed by MongoDB with tenant-scoped collections.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from connector_sdk.mdu_schema import MDUEntityType, MDURecord


class MasterDB:
    """
    In-memory MasterDB for runtime validation.
    Production implementation replaces this with MongoDB adapter.
    """

    def __init__(self):
        # {tenant_id: {entity_type: {idempotency_key: MDURecord}}}
        self._store: Dict[str, Dict[str, Dict[str, MDURecord]]] = defaultdict(
            lambda: defaultdict(dict)
        )

    def upsert(self, record: MDURecord) -> bool:
        """
        Insert or update a record by idempotency_key.
        Returns True if inserted, False if updated (duplicate).
        """
        bucket = self._store[record.tenant_id][record.entity_type.value]
        is_new = record.idempotency_key not in bucket
        bucket[record.idempotency_key] = record
        return is_new

    def get(self, tenant_id: str, entity_type: MDUEntityType, idempotency_key: str) -> Optional[MDURecord]:
        return self._store[tenant_id][entity_type.value].get(idempotency_key)

    def list_by_type(self, tenant_id: str, entity_type: MDUEntityType) -> List[MDURecord]:
        return list(self._store[tenant_id][entity_type.value].values())

    def count(self, tenant_id: str, entity_type: Optional[MDUEntityType] = None) -> int:
        if entity_type:
            return len(self._store[tenant_id][entity_type.value])
        return sum(len(v) for v in self._store[tenant_id].values())

    def snapshot(self, tenant_id: str) -> Dict[str, Any]:
        """Return a summary snapshot for observability."""
        return {
            "tenant_id": tenant_id,
            "entity_counts": {
                etype: len(records)
                for etype, records in self._store[tenant_id].items()
            },
            "total_records": self.count(tenant_id),
        }
