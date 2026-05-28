"""Tests for the MangaPlus title-discovery gateway adapter."""

from __future__ import annotations

import pytest

from mloader.infrastructure.mangaplus import title_discovery


def test_gateway_delegates_to_title_discovery_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify gateway methods delegate to module helpers with expected arguments."""
    gateway = title_discovery.MangaPlusTitleDiscoveryGateway()
    calls: dict[str, object] = {}

    def _parse_language_filters(languages: tuple[str, ...]) -> set[int]:
        calls["languages"] = languages
        return {7}

    def _collect_title_ids_from_api(
        endpoint: str,
        *,
        id_length: int | None,
        allowed_languages: set[int] | None,
        request_timeout: tuple[float, float],
        capture_api_dir: str | None,
    ) -> list[int]:
        calls["api"] = (
            endpoint,
            id_length,
            allowed_languages,
            request_timeout,
            capture_api_dir,
        )
        return [100001]

    def _collect_title_ids(
        pages: tuple[str, ...],
        *,
        id_length: int | None,
        request_timeout: tuple[float, float],
    ) -> list[int]:
        calls["static"] = (pages, id_length, request_timeout)
        return [100002]

    def _collect_title_ids_with_browser(
        pages: tuple[str, ...],
        *,
        id_length: int | None,
        timeout_ms: int,
    ) -> list[int]:
        calls["browser"] = (pages, id_length, timeout_ms)
        return [100003]

    monkeypatch.setattr(
        title_discovery.title_index, "parse_language_filters", _parse_language_filters
    )
    monkeypatch.setattr(
        title_discovery.title_index,
        "collect_title_ids_from_api",
        _collect_title_ids_from_api,
    )
    monkeypatch.setattr(title_discovery.static_discovery, "collect_title_ids", _collect_title_ids)
    monkeypatch.setattr(
        title_discovery.browser_discovery,
        "collect_title_ids_with_browser",
        _collect_title_ids_with_browser,
    )

    assert gateway.parse_language_filters(("german",)) == {7}
    assert gateway.collect_title_ids_from_api(
        "https://example.com/allV2",
        id_length=6,
        allowed_languages={7},
        request_timeout=(1.0, 2.0),
        capture_api_dir="/tmp/capture",
    ) == [100001]
    assert gateway.collect_title_ids(
        ("https://example.com/list",),
        id_length=None,
        request_timeout=(3.0, 4.0),
    ) == [100002]
    assert gateway.collect_title_ids_with_browser(
        ("https://example.com/list",),
        id_length=5,
        timeout_ms=123,
    ) == [100003]

    assert calls == {
        "languages": ("german",),
        "api": ("https://example.com/allV2", 6, {7}, (1.0, 2.0), "/tmp/capture"),
        "static": (("https://example.com/list",), None, (3.0, 4.0)),
        "browser": (("https://example.com/list",), 5, 123),
    }
