"""
SETU Connector Auth Boundary — Bright Connection

Credentials are injected from environment variables only.
Never committed to Git. Never appear in MDURecord or evidence payloads.

Usage:
    from connectors.bright_connection.auth import load_connector_config
    config = load_connector_config("bright_orders")

Environment variables required per connector:
    SETU_BA_API_KEY              biz_analyst
    SETU_BA_BASE_URL             biz_analyst
    SETU_CRM_OAUTH_TOKEN         bright_crm
    SETU_DMS_API_KEY             bright_dms
    SETU_INV_API_KEY             bright_inventory
    SETU_ORDERS_API_KEY          bright_orders
    SETU_SALES_API_KEY           bright_sales
    SETU_COLLECTIONS_API_KEY     bright_collections
    SETU_DEALER_API_KEY          bright_dealer
    SETU_TALLY_HOST              tally (default: 192.168.0.72)
    SETU_TALLY_PORT              tally (default: 9000)

If an env var is not set, the connector falls back to test/stub mode.
Stub mode is explicitly flagged in the config dict as {"_stub_mode": True}.
"""
from __future__ import annotations

import os
from typing import Any, Dict


_ENV_MAP: Dict[str, Dict[str, str]] = {
    "biz_analyst": {
        "api_key": "SETU_BA_API_KEY",
        "base_url": "SETU_BA_BASE_URL",
    },
    "bright_crm": {
        "oauth_token": "SETU_CRM_OAUTH_TOKEN",
        "base_url": "SETU_CRM_BASE_URL",
    },
    "bright_dms": {
        "api_key": "SETU_DMS_API_KEY",
        "base_url": "SETU_DMS_BASE_URL",
    },
    "bright_inventory": {
        "api_key": "SETU_INV_API_KEY",
        "base_url": "SETU_INV_BASE_URL",
    },
    "bright_orders": {
        "api_key": "SETU_ORDERS_API_KEY",
        "base_url": "SETU_ORDERS_BASE_URL",
    },
    "bright_sales": {
        "api_key": "SETU_SALES_API_KEY",
        "base_url": "SETU_SALES_BASE_URL",
    },
    "bright_collections": {
        "api_key": "SETU_COLLECTIONS_API_KEY",
        "base_url": "SETU_COLLECTIONS_BASE_URL",
    },
    "bright_dealer": {
        "api_key": "SETU_DEALER_API_KEY",
        "base_url": "SETU_DEALER_BASE_URL",
    },
    "tally": {
        "tally_host": "SETU_TALLY_HOST",
        "tally_port": "SETU_TALLY_PORT",
    },
}

_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "biz_analyst": {"base_url": "https://api.bizanalyst.in/v1"},
    "tally": {"tally_host": "192.168.0.72", "tally_port": "9000"},
}


def load_connector_config(connector_id: str) -> Dict[str, Any]:
    """
    Build connector config from environment variables.
    Returns config dict with _stub_mode=True if any required credential is missing.
    Credentials are never logged or included in MDURecord.
    """
    env_keys = _ENV_MAP.get(connector_id, {})
    defaults = _DEFAULTS.get(connector_id, {})
    config: Dict[str, Any] = {}
    missing = []

    for config_key, env_var in env_keys.items():
        value = os.environ.get(env_var)
        if value:
            config[config_key] = value
        elif config_key in defaults:
            config[config_key] = defaults[config_key]
        else:
            missing.append(env_var)

    config["_stub_mode"] = len(missing) > 0
    config["_missing_env_vars"] = missing
    return config


def is_stub_mode(config: Dict[str, Any]) -> bool:
    return config.get("_stub_mode", True)


def redact_for_evidence(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy of config safe for evidence/logging — credentials redacted.
    """
    sensitive = {"api_key", "oauth_token", "password", "secret", "token"}
    return {
        k: "<redacted>" if k in sensitive else v
        for k, v in config.items()
        if not k.startswith("_")
    }
