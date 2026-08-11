"""
SETU Connector SDK
Canonical base contracts for all external system connectors.
"""
from .base_connector import BaseConnector, ConnectorManifest, ConnectorCategory, ConnectorStatus
from .mdu_schema import MDURecord, MDUEntityType
from .registry import ConnectorRegistry
from .runtime_contract import ConnectorRuntimeContract, ConnectorEvent, ConnectorError

__all__ = [
    "BaseConnector",
    "ConnectorManifest",
    "ConnectorCategory",
    "ConnectorStatus",
    "MDURecord",
    "MDUEntityType",
    "ConnectorRegistry",
    "ConnectorRuntimeContract",
    "ConnectorEvent",
    "ConnectorError",
]
