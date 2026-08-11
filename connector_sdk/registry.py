"""
ConnectorRegistry — central catalog of all registered connectors.

Connectors register once. Tenants bind connector instances via config.
SETU core never imports connector implementations directly.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Type

from .base_connector import BaseConnector, ConnectorCategory, ConnectorManifest


class ConnectorRegistrationError(Exception):
    pass


class ConnectorRegistry:
    """
    Singleton registry mapping connector_id → connector class.
    Tenant instances are created on demand via create_instance().
    """
    _connectors: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, connector_class: Type[BaseConnector]) -> None:
        manifest = connector_class.__new__(connector_class)
        # Peek at manifest without full init
        try:
            cid = connector_class._connector_id
        except AttributeError:
            raise ConnectorRegistrationError(
                f"{connector_class.__name__} must define _connector_id class attribute"
            )
        if cid in cls._connectors:
            raise ConnectorRegistrationError(f"Connector '{cid}' already registered")
        cls._connectors[cid] = connector_class

    @classmethod
    def get(cls, connector_id: str) -> Optional[Type[BaseConnector]]:
        return cls._connectors.get(connector_id)

    @classmethod
    def create_instance(
        cls,
        connector_id: str,
        tenant_id: str,
        config: dict,
    ) -> BaseConnector:
        klass = cls.get(connector_id)
        if klass is None:
            raise ConnectorRegistrationError(f"Connector '{connector_id}' not registered")
        return klass(tenant_id=tenant_id, config=config)

    @classmethod
    def list_all(cls) -> List[Dict]:
        result = []
        for cid, klass in cls._connectors.items():
            # Instantiate a dummy to read manifest safely
            try:
                dummy = klass.__new__(klass)
                dummy.tenant_id = "_probe"
                dummy._config = {}
                dummy._status = None
                dummy._last_sync = None
                manifest = dummy.manifest
                result.append(manifest.to_dict())
            except Exception:
                result.append({"connector_id": cid, "status": "manifest_unavailable"})
        return result

    @classmethod
    def list_by_category(cls, category: ConnectorCategory) -> List[str]:
        matches = []
        for cid, klass in cls._connectors.items():
            try:
                dummy = klass.__new__(klass)
                dummy.tenant_id = "_probe"
                dummy._config = {}
                dummy._status = None
                dummy._last_sync = None
                if dummy.manifest.category == category:
                    matches.append(cid)
            except Exception:
                pass
        return matches
