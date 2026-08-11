"""
TenantLoader — reads tenant config and instantiates connectors.

Onboarding a new tenant requires only:
  1. Create tenant config JSON
  2. Register connectors in ConnectorRegistry
  3. Call TenantLoader.load()

Zero source-code modification to SETU core.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from connector_sdk.registry import ConnectorRegistry
from connector_sdk.base_connector import BaseConnector


class TenantLoader:

    @staticmethod
    def load(config_path: str) -> Dict[str, Any]:
        """
        Load tenant config and return instantiated connector map.
        Returns: {connector_id: BaseConnector instance}
        """
        with open(config_path, "r") as f:
            config = json.load(f)

        tenant_id = config["tenant_id"]
        connector_instances: Dict[str, BaseConnector] = {}

        for conn_cfg in config.get("connectors", []):
            if not conn_cfg.get("enabled", True):
                continue
            cid = conn_cfg["connector_id"]
            auth = conn_cfg.get("auth", {})
            instance_config = {**auth, "entity_types": conn_cfg.get("entity_types", [])}
            try:
                instance = ConnectorRegistry.create_instance(cid, tenant_id, instance_config)
                connector_instances[cid] = instance
            except Exception as e:
                print(f"[TenantLoader] WARNING: Could not instantiate connector '{cid}': {e}")

        return {
            "tenant_id": tenant_id,
            "tenant_name": config.get("tenant_name"),
            "modules": config.get("modules", []),
            "roles": config.get("roles", []),
            "policies": config.get("policies", []),
            "connectors": connector_instances,
        }
