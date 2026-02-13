import importlib

import mloader.config as config


def test_auth_params_respect_environment(monkeypatch):
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
