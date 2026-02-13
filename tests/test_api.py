"""Tests for API helper functions and caching mixin methods."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from mloader.manga_loader import api


class DummySession:
    """HTTP session test double collecting outgoing requests."""

    def __init__(self, content: bytes = b"payload") -> None:
        """Initialize a dummy session returning ``content`` responses."""
        self.content = content
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> SimpleNamespace:
        """Record request details and return a simple response object."""
        del timeout
        self.calls.append((url, params))
        return SimpleNamespace(content=self.content, raise_for_status=lambda: None)


class DummyLoader(api.APILoaderMixin):
    """APILoaderMixin harness with controllable split and quality values."""

    def __init__(self, split: bool = True, quality: str = "high") -> None:
        """Initialize loader state with a dummy session."""
        self._api_url = "https://api.example"
        self.split = split
        self.quality = quality
        self.request_timeout = (1.0, 2.0)
        self.session = DummySession()


def test_parse_manga_viewer_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify viewer parser extracts ``success.manga_viewer`` payload."""
    sentinel = object()

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            """Return a namespaced response carrying a manga viewer sentinel."""
            return SimpleNamespace(success=SimpleNamespace(manga_viewer=sentinel))

    monkeypatch.setattr(api, "Response", FakeResponse)

    assert api._parse_manga_viewer_response(b"raw") is sentinel


def test_parse_title_detail_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify title-detail parser extracts ``success.title_detail_view`` payload."""
    sentinel = object()

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            """Return a namespaced response carrying a title-detail sentinel."""
            return SimpleNamespace(success=SimpleNamespace(title_detail_view=sentinel))

    monkeypatch.setattr(api, "Response", FakeResponse)

    assert api._parse_title_detail_response(b"raw") is sentinel


def test_build_title_detail_params_includes_auth_values() -> None:
    """Verify title-detail parameter builder includes auth and title ID."""
    params = api._build_title_detail_params(123)

    assert params["title_id"] == 123
    assert "app_ver" in params
    assert "secret" in params


def test_manga_viewer_url_and_params() -> None:
    """Verify viewer URL and query parameter builder output."""
    loader = DummyLoader(split=False, quality="low")

    assert loader._build_manga_viewer_url() == "https://api.example/api/manga_viewer"

    params = loader._build_manga_viewer_params(10)
    assert params["chapter_id"] == 10
    assert params["split"] == "no"
    assert params["img_quality"] == "low"


def test_load_pages_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify load_pages uses LRU cache for repeated chapter lookups."""
    api.APILoaderMixin._load_pages.cache_clear()
    loader = DummyLoader()

    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})

    first = loader._load_pages(5)
    second = loader._load_pages(5)

    assert first == {"parsed": b"payload"}
    assert second == first
    assert len(loader.session.calls) == 1


def test_get_title_details_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_title_details uses LRU cache for repeated title lookups."""
    api.APILoaderMixin._get_title_details.cache_clear()
    loader = DummyLoader()

    monkeypatch.setattr(api, "_parse_title_detail_response", lambda content: {"parsed": content})

    first = loader._get_title_details(77)
    second = loader._get_title_details(77)

    assert first == {"parsed": b"payload"}
    assert second == first
    assert len(loader.session.calls) == 1


def test_title_detail_url() -> None:
    """Verify title-detail endpoint URL is built correctly."""
    loader = DummyLoader()
    assert loader._build_title_detail_url() == "https://api.example/api/title_detailV3"
