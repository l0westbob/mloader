"""Tests for environment-backed configuration values."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import mloader.config as config


def test_auth_params_respect_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure AUTH_PARAMS reflects environment overrides after reload."""
    monkeypatch.setenv("APP_VER", "999")
    monkeypatch.setenv("OS", "android")
    monkeypatch.setenv("OS_VER", "42")
    monkeypatch.setenv("SECRET", "secret-value")

    reloaded = importlib.reload(config)

    assert reloaded.AUTH_PARAMS == {
        "app_ver": "999",
        "os": "android",
        "os_ver": "42",
        "secret": "secret-value",
    }


def test_load_auth_settings_uses_file_when_env_is_missing(tmp_path: Path) -> None:
    """Ensure file-based auth config is used when no env overrides are present."""
    config_file = tmp_path / ".mloader.toml"
    config_file.write_text(
        '[auth]\napp_ver = "123"\nos = "android"\nos_ver = "14.0"\nsecret = "from-file"\n',
        encoding="utf-8",
    )

    settings = config.load_auth_settings(environ={}, config_file=config_file)

    assert settings.as_query_params() == {
        "app_ver": "123",
        "os": "android",
        "os_ver": "14.0",
        "secret": "from-file",
    }


def test_load_auth_settings_uses_env_over_file(tmp_path: Path) -> None:
    """Ensure environment values override config-file values by key."""
    config_file = tmp_path / ".mloader.toml"
    config_file.write_text(
        '[auth]\napp_ver = "123"\nos = "android"\nos_ver = "14.0"\nsecret = "from-file"\n',
        encoding="utf-8",
    )

    settings = config.load_auth_settings(
        environ={
            "APP_VER": "999",
            "OS": "ios",
            "OS_VER": "18.1",
            "SECRET": "from-env",
        },
        config_file=config_file,
    )

    assert settings.as_query_params() == {
        "app_ver": "999",
        "os": "ios",
        "os_ver": "18.1",
        "secret": "from-env",
    }


def test_load_auth_settings_uses_overrides_over_env_and_file(tmp_path: Path) -> None:
    """Ensure explicit overrides are highest-priority values."""
    config_file = tmp_path / ".mloader.toml"
    config_file.write_text('[auth]\napp_ver = "111"\nos = "android"\n', encoding="utf-8")

    settings = config.load_auth_settings(
        environ={"APP_VER": "222", "OS": "ios"},
        config_file=config_file,
        overrides={"app_ver": "333"},
    )

    assert settings.app_ver == "333"
    assert settings.os == "ios"


def test_load_auth_settings_rejects_unknown_override_key() -> None:
    """Ensure unknown override keys fail fast with explicit error message."""
    with pytest.raises(ValueError, match="Unsupported auth override key"):
        config.load_auth_settings(overrides={"unknown": "value"})


def test_load_auth_settings_ignores_missing_config_file_path() -> None:
    """Ensure missing config file paths are treated as empty config data."""
    settings = config.load_auth_settings(environ={}, config_file="/tmp/does-not-exist-mloader.toml")

    assert settings.as_query_params() == {
        "app_ver": "97",
        "os": "ios",
        "os_ver": "18.1",
        "secret": "f40080bcb01a9a963912f46688d411a3",
    }


def test_load_auth_settings_uses_env_config_file_path(tmp_path: Path) -> None:
    """Ensure MLOADER_CONFIG_FILE path is used when explicit path is omitted."""
    config_file = tmp_path / "custom.toml"
    config_file.write_text('[auth]\napp_ver = "777"\n', encoding="utf-8")

    settings = config.load_auth_settings(
        environ={"MLOADER_CONFIG_FILE": str(config_file)},
        config_file=None,
    )

    assert settings.app_ver == "777"


def test_load_auth_settings_reads_default_config_file_from_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure default .mloader.toml is discovered from current working directory."""
    default_config = tmp_path / ".mloader.toml"
    default_config.write_text('[auth]\nsecret = "from-default"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = config.load_auth_settings(environ={}, config_file=None)

    assert settings.secret == "from-default"


def test_load_auth_settings_invalid_auth_table_type_raises(tmp_path: Path) -> None:
    """Ensure invalid [auth] shape fails fast with explicit error details."""
    config_file = tmp_path / ".mloader.toml"
    config_file.write_text('auth = "invalid"', encoding="utf-8")

    with pytest.raises(ValueError, match="\\[auth\\] section must be a table"):
        config.load_auth_settings(environ={}, config_file=config_file)


def test_load_auth_settings_missing_auth_section_uses_defaults(tmp_path: Path) -> None:
    """Ensure config files without [auth] section do not override defaults."""
    config_file = tmp_path / ".mloader.toml"
    config_file.write_text('[other]\nvalue = "x"\n', encoding="utf-8")

    settings = config.load_auth_settings(environ={}, config_file=config_file)

    assert settings.as_query_params()["app_ver"] == "97"
