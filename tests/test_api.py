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
        self.payload_capture = None


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
    """Verify load_pages uses cache for repeated chapter lookups."""
    loader = DummyLoader()

    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})

    first = loader._load_pages(5)
    second = loader._load_pages(5)

    assert first == {"parsed": b"payload"}
    assert second == first
    assert len(loader.session.calls) == 1


def test_get_title_details_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_title_details uses cache for repeated title lookups."""
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


def test_load_pages_captures_payload_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _load_pages forwards response payloads to capture backend."""
    loader = DummyLoader()
    captured: list[dict[str, Any]] = []

    class Capture:
        def capture(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    loader.payload_capture = Capture()
    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})

    loader._load_pages(123)

    assert len(captured) == 1
    assert captured[0]["endpoint"] == "manga_viewer"
    assert captured[0]["identifier"] == 123
    assert captured[0]["url"].endswith("/api/manga_viewer")
    assert captured[0]["response_content"] == b"payload"


def test_get_title_details_captures_payload_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _get_title_details forwards response payloads to capture backend."""
    loader = DummyLoader()
    captured: list[dict[str, Any]] = []

    class Capture:
        def capture(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    loader.payload_capture = Capture()
    monkeypatch.setattr(api, "_parse_title_detail_response", lambda content: {"parsed": content})

    loader._get_title_details(88)

    assert len(captured) == 1
    assert captured[0]["endpoint"] == "title_detailV3"
    assert captured[0]["identifier"] == 88
    assert captured[0]["url"].endswith("/api/title_detailV3")
    assert captured[0]["response_content"] == b"payload"


def test_clear_api_caches_for_run_empties_both_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run-level clear removes cached title and chapter responses."""
    loader = DummyLoader()
    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})
    monkeypatch.setattr(api, "_parse_title_detail_response", lambda content: {"parsed": content})

    loader._load_pages(1)
    loader._get_title_details(2)
    assert loader._get_viewer_cache()
    assert loader._get_title_cache()

    loader._clear_api_caches_for_run()

    assert loader._get_viewer_cache() == {}
    assert loader._get_title_cache() == {}


def test_clear_api_caches_for_title_removes_selected_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify title-level clear removes the requested title and chapter cache entries."""
    loader = DummyLoader()
    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})
    monkeypatch.setattr(api, "_parse_title_detail_response", lambda content: {"parsed": content})

    loader._load_pages(10)
    loader._load_pages(11)
    loader._get_title_details(20)
    loader._get_title_details(21)

    loader._clear_api_caches_for_title(20, [10])

    assert "20" not in loader._get_title_cache()
    assert "21" in loader._get_title_cache()
    assert "10" not in loader._get_viewer_cache()
    assert "11" in loader._get_viewer_cache()


def test_clear_api_caches_for_title_without_chapters_only_clears_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify title-only clear keeps viewer cache entries intact."""
    loader = DummyLoader()
    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})
    monkeypatch.setattr(api, "_parse_title_detail_response", lambda content: {"parsed": content})

    loader._load_pages(10)
    loader._get_title_details(20)

    loader._clear_api_caches_for_title(20, None)

    assert "20" not in loader._get_title_cache()
    assert "10" in loader._get_viewer_cache()


def test_load_pages_cache_respects_max_size(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify chapter cache evicts oldest entries when max size is exceeded."""
    loader = DummyLoader()
    loader._viewer_cache_max_size = 2
    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})

    loader._load_pages(1)
    loader._load_pages(2)
    loader._load_pages(3)

    assert set(loader._get_viewer_cache().keys()) == {"2", "3"}


def test_get_title_details_cache_respects_max_size(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify title cache evicts oldest entries when max size is exceeded."""
    loader = DummyLoader()
    loader._title_cache_max_size = 1
    monkeypatch.setattr(api, "_parse_title_detail_response", lambda content: {"parsed": content})

    loader._get_title_details(1)
    loader._get_title_details(2)

    assert set(loader._get_title_cache().keys()) == {"2"}
