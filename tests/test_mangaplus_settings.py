"""Tests for centralized MangaPlus infrastructure settings and auth helpers."""

from __future__ import annotations

from mloader import config
from mloader.config import AuthSettings
from mloader.infrastructure.mangaplus import auth, settings


def test_api_url_joins_base_url_and_endpoint_path() -> None:
    """Verify MangaPlus endpoint URLs are composed consistently."""
    assert (
        settings.api_url("https://jumpg-api.tokyo-cdn.com/", "/api/manga_viewer")
        == "https://jumpg-api.tokyo-cdn.com/api/manga_viewer"
    )


def test_default_title_index_endpoint_uses_central_api_base() -> None:
    """Verify title-index endpoint is derived from central API settings."""
    assert settings.DEFAULT_TITLE_INDEX_ENDPOINT == settings.api_url(
        settings.DEFAULT_API_BASE_URL,
        settings.TITLE_INDEX_PATH,
    )


def test_auth_params_returns_configured_settings_mapping() -> None:
    """Verify MangaPlus auth helper renders settings as query params."""
    custom = AuthSettings(app_ver="1", os="android", os_ver="14", secret="secret")

    assert auth.auth_params(custom) == {
        "app_ver": "1",
        "os": "android",
        "os_ver": "14",
        "secret": "secret",
    }
    assert auth.auth_params() == config.AUTH_SETTINGS.as_query_params()
    assert set(auth.auth_params()) == {"app_ver", "os", "os_ver", "secret"}
