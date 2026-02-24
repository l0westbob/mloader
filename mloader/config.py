"""Typed immutable runtime settings with layered configuration resolution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib
from typing import Mapping

from dotenv import load_dotenv

load_dotenv()

_DEFAULT_AUTH_SETTINGS: dict[str, str] = {
    "app_ver": "97",
    "os": "ios",
    "os_ver": "18.1",
    "secret": "f40080bcb01a9a963912f46688d411a3",
}
_ENV_TO_FIELD_MAP: dict[str, str] = {
    "APP_VER": "app_ver",
    "OS": "os",
    "OS_VER": "os_ver",
    "SECRET": "secret",
}
_DEFAULT_CONFIG_FILE = ".mloader.toml"


@dataclass(frozen=True, slots=True)
class AuthSettings:
    """Immutable auth-related settings required for MangaPlus API requests."""

    app_ver: str
    os: str
    os_ver: str
    secret: str

    def as_query_params(self) -> dict[str, str]:
        """Return settings as API query parameter mapping."""
        return {
            "app_ver": self.app_ver,
            "os": self.os,
            "os_ver": self.os_ver,
            "secret": self.secret,
        }


def _load_auth_from_file(config_file: str | Path | None) -> dict[str, str]:
    """Load auth settings from TOML file, returning empty mapping when unavailable."""
    if config_file is None:
        return {}

    config_path = Path(config_file)
    if not config_path.exists() or not config_path.is_file():
        return {}

    parsed_config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    auth_section = parsed_config.get("auth")
    if auth_section is None:
        return {}
    if not isinstance(auth_section, dict):
        raise ValueError("Invalid config file: [auth] section must be a table")

    resolved: dict[str, str] = {}
    for key in _DEFAULT_AUTH_SETTINGS:
        value = auth_section.get(key)
        if value is None:
            continue
        resolved[key] = str(value)
    return resolved


def _resolve_config_file(environ: Mapping[str, str], config_file: str | Path | None) -> str | Path | None:
    """Resolve config file location from explicit argument, env var, or default path."""
    if config_file is not None:
        return config_file

    env_config_file = environ.get("MLOADER_CONFIG_FILE")
    if env_config_file:
        return env_config_file

    default_path = Path(_DEFAULT_CONFIG_FILE)
    if default_path.exists() and default_path.is_file():
        return default_path
    return None


def load_auth_settings(
    *,
    overrides: Mapping[str, str] | None = None,
    environ: Mapping[str, str] | None = None,
    config_file: str | Path | None = None,
) -> AuthSettings:
    """Load immutable auth settings with layered priority resolution.

    Resolution order (highest to lowest):
    1. ``overrides`` (CLI/runtime injected values)
    2. environment variables
    3. TOML config file (explicit path, env-selected path, or default)
    4. built-in defaults
    """
    resolved_environ = environ if environ is not None else os.environ

    merged: dict[str, str] = dict(_DEFAULT_AUTH_SETTINGS)
    resolved_config_file = _resolve_config_file(resolved_environ, config_file)
    merged.update(_load_auth_from_file(resolved_config_file))

    for env_key, field_name in _ENV_TO_FIELD_MAP.items():
        env_value = resolved_environ.get(env_key)
        if env_value is not None:
            merged[field_name] = env_value

    if overrides:
        for key, value in overrides.items():
            if key not in _DEFAULT_AUTH_SETTINGS:
                raise ValueError(f"Unsupported auth override key: {key}")
            merged[key] = str(value)

    return AuthSettings(**merged)


AUTH_SETTINGS = load_auth_settings()
AUTH_PARAMS = AUTH_SETTINGS.as_query_params()
