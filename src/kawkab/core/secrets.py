"""Secrets management for API keys and sensitive configuration.

Loads API keys from environment variables first, then from a JSON file
at ~/.kawkab/secrets.json (Unix) or %%APPDATA%%/KawkabAI/secrets.json (Windows).
No secrets are hardcoded in source code.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _secrets_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "KawkabAI" / "secrets.json"
    return Path.home() / ".kawkab" / "secrets.json"


def _ensure_secrets_dir() -> Path:
    path = _secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_secrets() -> dict[str, Any]:
    path = _secrets_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_secrets(data: dict[str, Any]) -> None:
    path = _ensure_secrets_dir()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def get_api_key(service_name: str) -> str | None:
    """Get an API key for *service_name*.

    Checks environment variable ``{SERVICE_NAME}_API_KEY`` (uppercased)
    first, then falls back to the secrets file on disk.

    Args:
        service_name: e.g. ``"football_data"``, ``"statsbomb"``.

    Returns:
        The API key string, or ``None`` if not found.
    """
    env_var = f"{service_name.upper()}_API_KEY"
    value = os.environ.get(env_var)
    if value:
        return value
    secrets = _load_secrets()
    return secrets.get(service_name)


def set_api_key(service_name: str, key: str) -> None:
    """Persist an API key for *service_name* to the secrets file.

    Args:
        service_name: e.g. ``"football_data"``.
        key: The API key string.
    """
    secrets = _load_secrets()
    secrets[service_name] = key
    _save_secrets(secrets)


def list_services() -> list[str]:
    """Return known service names from the secrets file.

    Returns:
        Sorted list of service names that have stored keys.
    """
    return sorted(_load_secrets().keys())


def delete_api_key(service_name: str) -> bool:
    """Remove a stored API key.

    Args:
        service_name: The service to remove.

    Returns:
        True if the key existed and was removed, False otherwise.
    """
    secrets = _load_secrets()
    if service_name not in secrets:
        return False
    del secrets[service_name]
    _save_secrets(secrets)
    return True
