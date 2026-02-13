"""Tests for environment-backed configuration values."""

from __future__ import annotations

import importlib

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
