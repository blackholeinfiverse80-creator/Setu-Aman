"""
MasterDB — canonical enterprise data store.

Accepts only MDURecord instances.
Enforces idempotency via idempotency_key.
Tenant-isolated: no cross-tenant reads.

Storage backend:
  - PRODUCTION: MongoDB adapter (provided by KAVY/MDU ecosystem boundary)
  - LOCAL/INTEGRATION: SQLite file-backed store (proves persistence across restart)
  - VALIDATION: In-memory fallback (original behaviour, used by validate_runtime.py)

Backend is selected by environment variable SETU_MASTERDB_BACKEND:
  "sqlite"   -> file-backed SQLite (default for integration testing)
  "memory"   -> in-memory (original, for validate_runtime.py compatibility)
  "mongodb"  -> MongoDB (production, requires SETU_MASTERDB_MONGO_URI)
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connector_sdk.mdu_schema import MDUEntityType, MDURecord


# ── Backend selection ──────────────────────────────────────────────────────────

_BACKEND = os.environ.get("SETU_MASTERDB_BACKEND", "memory").lower()
_SQLITE_PATH = os.environ.get(
    "SETU_MASTERDB_SQLITE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "masterdb.sqlite"),
)


# ── SQLite backend ─────────────────────────────────────────────────────────────

class _SQLiteStore:
    """
    File-backed SQLite store.
    Proves persistence across process restart.
    Schema: one table, tenant-partitioned by tenant_id column.
    """

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mdu_records (
                    idempotency_key TEXT NOT NULL,
                    tenant_id       TEXT NOT NULL,
                    entity_type     TEXT NOT NULL,
                    entity_id       TEXT NOT NULL,
                    source_connector TEXT NOT NULL,
                    trace_id        TEXT NOT NULL,
                    schema_version  TEXT NOT NULL DEFAULT '1.0',
                    canonical_data  TEXT NOT NULL,
                    integrity_hash  TEXT NOT NULL,
                    ingested_at     TEXT NOT NULL,
                    raw_ref         TEXT,
                    tags            TEXT NOT NULL DEFAULT '[]',
                    metadata        TEXT NOT NULL DEFAULT '{}',
                    upserted_at     TEXT NOT NULL,
                    PRIMARY KEY (idempotency_key, tenant_id)
                )
            """)
            conn.commit()

    def upsert(self, record: MDURecord) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT idempotency_key FROM mdu_records WHERE idempotency_key=? AND tenant_id=?",
                (record.idempotency_key, record.tenant_id),
            ).fetchone()
            is_new = existing is None
            conn.execute("""
                INSERT OR REPLACE INTO mdu_records
                (idempotency_key, tenant_id, entity_type, entity_id, source_connector,
                 trace_id, schema_version, canonical_data, integrity_hash, ingested_at,
                 raw_ref, tags, metadata, upserted_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.idempotency_key,
                record.tenant_id,
                record.entity_type.value,
                record.entity_id,
                record.source_connector,
                record.trace_id,
                record.schema_version,
                json.dumps(record.canonical_data, default=str),
                record.integrity_hash(),
                record.ingested_at,
                record.raw_ref,
                json.dumps(record.tags),
                json.dumps(record.metadata),
                now,
            ))
            conn.commit()
        return is_new

    def get(self, tenant_id: str, entity_type: MDUEntityType, idempotency_key: str) -> Optional[MDURecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM mdu_records WHERE idempotency_key=? AND tenant_id=? AND entity_type=?",
                (idempotency_key, tenant_id, entity_type.value),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_by_type(self, tenant_id: str, entity_type: MDUEntityType) -> List[MDURecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mdu_records WHERE tenant_id=? AND entity_type=?",
                (tenant_id, entity_type.value),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(self, tenant_id: str, entity_type: Optional[MDUEntityType] = None) -> int:
        with self._connect() as conn:
            if entity_type:
                return conn.execute(
                    "SELECT COUNT(*) FROM mdu_records WHERE tenant_id=? AND entity_type=?",
                    (tenant_id, entity_type.value),
                ).fetchone()[0]
            return conn.execute(
                "SELECT COUNT(*) FROM mdu_records WHERE tenant_id=?",
                (tenant_id,),
            ).fetchone()[0]

    def snapshot(self, tenant_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entity_type, COUNT(*) as cnt FROM mdu_records WHERE tenant_id=? GROUP BY entity_type",
                (tenant_id,),
            ).fetchall()
        entity_counts = {r["entity_type"]: r["cnt"] for r in rows}
        return {
            "tenant_id": tenant_id,
            "entity_counts": entity_counts,
            "total_records": sum(entity_counts.values()),
            "backend": "sqlite",
            "db_path": self._path,
        }

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MDURecord:
        return MDURecord(
            entity_type=MDUEntityType(row["entity_type"]),
            entity_id=row["entity_id"],
            tenant_id=row["tenant_id"],
            source_connector=row["source_connector"],
            canonical_data=json.loads(row["canonical_data"]),
            trace_id=row["trace_id"],
            schema_version=row["schema_version"],
            raw_ref=row["raw_ref"],
            ingested_at=row["ingested_at"],
            idempotency_key=row["idempotency_key"],
            tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]),
        )


# ── In-memory backend (original — preserves 45/45 validate_runtime.py) ────────

class _MemoryStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Dict[str, MDURecord]]] = defaultdict(
            lambda: defaultdict(dict)
        )

    def upsert(self, record: MDURecord) -> bool:
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
        return {
            "tenant_id": tenant_id,
            "entity_counts": {
                etype: len(records)
                for etype, records in self._store[tenant_id].items()
            },
            "total_records": self.count(tenant_id),
            "backend": "memory",
        }


# ── MongoDB stub (production boundary — provided by KAVY) ─────────────────────

class _MongoDBStore:
    """
    Production MasterDB boundary.
    This class is a STUB — the real implementation is owned by KAVY/MDU.
    It will raise NotImplementedError until the canonical boundary is provided.
    Replace this class body with the KAVY-provided MongoDB adapter.
    """

    def __init__(self):
        mongo_uri = os.environ.get("SETU_MASTERDB_MONGO_URI")
        if not mongo_uri:
            raise EnvironmentError(
                "SETU_MASTERDB_MONGO_URI environment variable required for MongoDB backend. "
                "This is the production MasterDB boundary owned by KAVY/MDU. "
                "Contact KAVY for the canonical adapter implementation."
            )
        # Placeholder — KAVY provides real implementation
        raise NotImplementedError(
            "MongoDB MasterDB backend is a production boundary owned by KAVY/MDU. "
            "Replace this stub with the canonical adapter when provided."
        )

    def upsert(self, record: MDURecord) -> bool:
        raise NotImplementedError

    def get(self, tenant_id: str, entity_type: MDUEntityType, idempotency_key: str) -> Optional[MDURecord]:
        raise NotImplementedError

    def list_by_type(self, tenant_id: str, entity_type: MDUEntityType) -> List[MDURecord]:
        raise NotImplementedError

    def count(self, tenant_id: str, entity_type: Optional[MDUEntityType] = None) -> int:
        raise NotImplementedError

    def snapshot(self, tenant_id: str) -> Dict[str, Any]:
        raise NotImplementedError


# ── MasterDB public interface ──────────────────────────────────────────────────

class MasterDB:
    """
    Canonical enterprise data store.

    Backend is selected by SETU_MASTERDB_BACKEND environment variable:
      "memory"  -> in-memory (default, used by validate_runtime.py — 45/45 preserved)
      "sqlite"  -> file-backed SQLite (integration testing, proves persistence)
      "mongodb" -> production boundary (KAVY-provided adapter required)

    The public interface is identical regardless of backend.
    Switching backends requires only an environment variable change — no code changes.
    """

    def __init__(self, backend: Optional[str] = None):
        selected = (backend or _BACKEND).lower()
        if selected == "sqlite":
            self._store = _SQLiteStore(_SQLITE_PATH)
        elif selected == "mongodb":
            self._store = _MongoDBStore()
        else:
            self._store = _MemoryStore()
        self._backend_name = selected

    @property
    def backend(self) -> str:
        return self._backend_name

    def upsert(self, record: MDURecord) -> bool:
        """
        Insert or update a record by idempotency_key.
        Returns True if inserted (new), False if updated (duplicate).
        Idempotent: same key always produces same canonical record.
        """
        return self._store.upsert(record)

    def get(self, tenant_id: str, entity_type: MDUEntityType, idempotency_key: str) -> Optional[MDURecord]:
        return self._store.get(tenant_id, entity_type, idempotency_key)

    def list_by_type(self, tenant_id: str, entity_type: MDUEntityType) -> List[MDURecord]:
        return self._store.list_by_type(tenant_id, entity_type)

    def count(self, tenant_id: str, entity_type: Optional[MDUEntityType] = None) -> int:
        return self._store.count(tenant_id, entity_type)

    def snapshot(self, tenant_id: str) -> Dict[str, Any]:
        """Return a summary snapshot for observability."""
        return self._store.snapshot(tenant_id)
