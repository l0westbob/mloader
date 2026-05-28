"""Tests for static MangaPlus list-page discovery."""

from __future__ import annotations

import pytest

from mloader.infrastructure.mangaplus import static_discovery
from tests.http_fakes import TextMappingSession


def test_extract_title_ids_respects_id_length_filter() -> None:
    """Verify HTML extraction keeps only IDs matching configured digit length."""
    html = (
        '<a href="/titles/123456">ok</a>'
        '<a href="/titles/10031">short</a>'
        '<a href="/titles/123456/">dup</a>'
    )
    assert static_discovery.extract_title_ids(html, id_length=6) == {123456}
    assert static_discovery.extract_title_ids(html, id_length=None) == {10031, 123456}


def test_extract_title_ids_matches_escaped_slash_links() -> None:
    """Verify extractor supports escaped JSON-style title links."""
    html = r'{"href":"\/titles\/123456\/"}{"href":"\/titles\/654321"}'
    assert static_discovery.extract_title_ids(html, id_length=None) == {123456, 654321}


def test_collect_title_ids_returns_sorted_unique_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify static scraper deduplicates IDs and returns sorted list."""
    payloads = {
        "https://a.example": '<a href="/titles/100003">A</a><a href="/titles/100001">B</a>',
        "https://b.example": '<a href="/titles/100001">C</a><a href="/titles/100002">D</a>',
    }
    dummy_session = TextMappingSession(payloads)
    monkeypatch.setattr(static_discovery.requests, "Session", lambda: dummy_session)

    result = static_discovery.collect_title_ids(
        ["https://a.example", "https://b.example"],
        id_length=6,
    )

    assert result == [100001, 100002, 100003]
    assert dummy_session.calls == [
        ("https://a.example", (5.0, 30.0)),
        ("https://b.example", (5.0, 30.0)),
    ]
