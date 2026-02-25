"""Tests for ID normalization logic."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable

import pytest

from mloader.manga_loader.normalization import NormalizationMixin


class DummyNormalizer(NormalizationMixin):
    """Normalization mixin harness with injected viewer/title fixtures."""

    def __init__(self, viewers: dict[int, Any], title_details: dict[int, Any]) -> None:
        """Store fake viewer and title-detail mappings used in tests."""
        self._viewers = viewers
        self._title_details = title_details

    def _load_pages(self, chapter_id: int) -> Any:
        """Return a pre-seeded manga viewer payload for ``chapter_id``."""
        return self._viewers[chapter_id]

    def _get_title_details(self, title_id: int) -> Any:
        """Return a pre-seeded title details payload for ``title_id``."""
        return self._title_details[title_id]


def _chapter(chapter_id: int, name: str) -> SimpleNamespace:
    """Build a minimal chapter object used in normalization inputs."""
    return SimpleNamespace(chapter_id=chapter_id, name=name)


def _group(chapters: Iterable[SimpleNamespace]) -> SimpleNamespace:
    """Build a chapter-list group containing the provided chapter sequence."""
    return SimpleNamespace(
        first_chapter_list=list(chapters),
        mid_chapter_list=[],
        last_chapter_list=[],
    )


def test_normalize_ids_requires_at_least_one_input() -> None:
    """Verify normalization rejects empty title and chapter input lists."""
    normalizer = DummyNormalizer({}, {})

    with pytest.raises(ValueError):
        normalizer._normalize_ids([], [], [], 0, 999)


def test_normalize_ids_uses_title_details_and_filters_by_chapter_numbers() -> None:
    """Verify title-only normalization resolves chapter numbers to chapter IDs."""
    title_details = {
        100312: SimpleNamespace(
            chapter_list_group=[
                _group(
                    [
                        _chapter(102277, "#1"),
                        _chapter(102278, "#2"),
                        _chapter(102279, "Special"),
                    ]
                )
            ]
        )
    }
    normalizer = DummyNormalizer({}, title_details)

    result = normalizer._normalize_ids([100312], [2], [], min_chapter=0, max_chapter=999)

    assert result == {100312: {102278}}


def test_normalize_ids_last_chapter_picks_only_final_entry() -> None:
    """Verify last_chapter mode returns only the final chapter ID."""
    title_details = {
        100312: SimpleNamespace(
            chapter_list_group=[
                _group(
                    [
                        _chapter(102277, "#102277"),
                        _chapter(102278, "#102278"),
                        _chapter(102279, "#102279"),
                    ]
                )
            ]
        )
    }
    normalizer = DummyNormalizer({}, title_details)

    result = normalizer._normalize_ids(
        [100312],
        [],
        [],
        min_chapter=0,
        max_chapter=2_147_483_647,
        last_chapter=True,
    )

    assert result == {100312: {102279}}


def test_normalize_ids_merges_chapter_id_and_title_number_requests() -> None:
    """Verify normalization merges chapter-ID and chapter-number-based targets."""
    viewers = {
        102277: SimpleNamespace(
            title_id=100312,
            chapter_id=102277,
            chapter_name="#1",
            chapters=[_chapter(102277, "#1"), _chapter(102278, "#2")],
        ),
        102377: SimpleNamespace(
            title_id=100412,
            chapter_id=102377,
            chapter_name="#7",
            chapters=[_chapter(102377, "#7")],
        ),
    }
    title_details = {
        100312: SimpleNamespace(
            chapter_list_group=[
                _group([_chapter(102277, "#1"), _chapter(102278, "#2"), _chapter(102279, "#3")])
            ]
        ),
        100412: SimpleNamespace(chapter_list_group=[_group([_chapter(102377, "#7")])]),
    }
    normalizer = DummyNormalizer(viewers, title_details)

    result = normalizer._normalize_ids(
        [100312],
        [2],
        [102377],
        min_chapter=0,
        max_chapter=2_147_483_647,
    )

    assert result == {100312: {102278}, 100412: {102377}}


def test_normalize_ids_prefers_viewer_chapters_when_chapter_id_matches_selected_title() -> None:
    """Verify overlapping title + chapter-ID inputs expand from viewer chapter list."""
    viewers = {
        102277: SimpleNamespace(
            title_id=100312,
            chapter_id=102277,
            chapter_name="#1",
            chapters=[_chapter(102277, "#1"), _chapter(102278, "#2")],
        )
    }
    normalizer = DummyNormalizer(viewers, {})

    result = normalizer._normalize_ids(
        [100312],
        [],
        [102277],
        min_chapter=0,
        max_chapter=2_147_483_647,
    )

    assert result == {100312: {102277, 102278}}


def test_normalize_ids_rejects_chapter_numbers_without_title_context() -> None:
    """Verify chapter-number-only requests fail without titles or chapter IDs."""
    normalizer = DummyNormalizer({}, {})

    with pytest.raises(ValueError, match="Chapter numbers require"):
        normalizer._normalize_ids([], [1], [], min_chapter=0, max_chapter=999)


def test_prepare_normalized_manga_list_delegates_to_normalize_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify wrapper method delegates to _normalize_ids and returns its result."""
    normalizer = DummyNormalizer({}, {})
    sentinel = {100312: {102277}}

    monkeypatch.setattr(
        normalizer,
        "_normalize_ids",
        lambda *args: sentinel,
    )

    result = normalizer._prepare_normalized_manga_list(
        [100312],
        [1],
        [102277],
        0,
        2_147_483_647,
        False,
    )
    assert result is sentinel


def test_normalization_mixin_placeholders_raise_not_implemented() -> None:
    """Verify default data-loading placeholders raise ``NotImplementedError``."""
    with pytest.raises(NotImplementedError):
        NormalizationMixin._load_pages(None, 1)  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError):
        NormalizationMixin._get_title_details(None, 1)  # type: ignore[arg-type]
