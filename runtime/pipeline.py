"""
ConnectorPipeline — canonical runtime orchestrator.

Flow:
  External System → Connector.sync() → MDURecord → MasterDB → Capability → Bucket → InsightFlow → Replay

Rules:
- Pipeline never imports connector business logic.
- All data flows as MDURecord.
- Tenant isolation enforced at every stage.
- Every record is replay-safe via idempotency_key.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connector_sdk.base_connector import BaseConnector
from connector_sdk.mdu_schema import MDURecord
from connector_sdk.runtime_contract import ConnectorEvent, ConnectorEventType, ConnectorError, ConnectorErrorCode
from .masterdb import MasterDB
from .insightflow import InsightFlow
from .replay import ReplayEngine


class PipelineResult:
    def __init__(self, trace_id: str, tenant_id: str, connector_id: str):
        self.trace_id = trace_id
        self.tenant_id = tenant_id
        self.connector_id = connector_id
        self.records_ingested: int = 0
        self.records_failed: int = 0
        self.events: List[Dict] = []
        self.errors: List[Dict] = []
        self.replay_keys: List[str] = []
        self.completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "connector_id": self.connector_id,
            "records_ingested": self.records_ingested,
            "records_failed": self.records_failed,
            "events": self.events,
            "errors": self.errors,
            "replay_keys": self.replay_keys,
            "completed_at": self.completed_at,
        }


class ConnectorPipeline:
    """
    Orchestrates the canonical data flow for a single connector sync.
    Stateless — one instance per sync run.
    """

    def __init__(
        self,
        masterdb: MasterDB,
        insightflow: InsightFlow,
        replay_engine: ReplayEngine,
    ):
        self._masterdb = masterdb
        self._insightflow = insightflow
        self._replay = replay_engine

    async def run(
        self,
        connector: BaseConnector,
        entity_types: List[str],
        params: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Execute full sync pipeline for a connector across given entity types.
        Returns PipelineResult with runtime evidence.
        """
        trace_id = f"trace_{connector.tenant_id}_{uuid.uuid4().hex[:12]}"
        connector._config["trace_id"] = trace_id
        result = PipelineResult(trace_id, connector.tenant_id, connector.manifest.connector_id)

        # Emit SYNC_STARTED
        start_event = ConnectorEvent.create(
            ConnectorEventType.SYNC_STARTED,
            connector.manifest.connector_id,
            connector.tenant_id,
            trace_id,
            {"entity_types": entity_types},
        )
        result.events.append(start_event.to_dict())

        for entity_type in entity_types:
            try:
                mdu_records = await connector.sync(entity_type, params)

                for record in mdu_records:
                    # Enforce tenant isolation
                    assert record.tenant_id == connector.tenant_id, "Tenant mismatch — record rejected"

                    # Write to MasterDB
                    self._masterdb.upsert(record)

                    # Dispatch to capability (InsightFlow)
                    self._insightflow.dispatch(record)

                    # Register for replay
                    self._replay.register(record)
                    result.replay_keys.append(record.idempotency_key)

                    result.records_ingested += 1

                # Emit DATA_RECEIVED
                result.events.append(ConnectorEvent.create(
                    ConnectorEventType.DATA_RECEIVED,
                    connector.manifest.connector_id,
                    connector.tenant_id,
                    trace_id,
                    {"entity_type": entity_type, "count": len(mdu_records)},
                ).to_dict())

            except AssertionError as e:
                err = ConnectorError.create(
                    ConnectorErrorCode.TENANT_MISMATCH,
                    connector.manifest.connector_id,
                    connector.tenant_id,
                    trace_id,
                    str(e),
                    retryable=False,
                )
                result.errors.append(err.to_dict())
                result.records_failed += 1

            except Exception as e:
                err = ConnectorError.create(
                    ConnectorErrorCode.EXTERNAL_SYSTEM_ERROR,
                    connector.manifest.connector_id,
                    connector.tenant_id,
                    trace_id,
                    str(e),
                    retryable=True,
                )
                result.errors.append(err.to_dict())
                result.records_failed += 1

        # Emit SYNC_COMPLETED
        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.events.append(ConnectorEvent.create(
            ConnectorEventType.SYNC_COMPLETED,
            connector.manifest.connector_id,
            connector.tenant_id,
            trace_id,
            {
                "records_ingested": result.records_ingested,
                "records_failed": result.records_failed,
            },
        ).to_dict())

        return result
