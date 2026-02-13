from types import SimpleNamespace

import pytest

from mloader.manga_loader.normalization import NormalizationMixin


class DummyNormalizer(NormalizationMixin):
    def __init__(self, viewers, title_details):
        self._viewers = viewers
        self._title_details = title_details

    def _load_pages(self, chapter_id):
        return self._viewers[chapter_id]

    def _get_title_details(self, title_id):
        return self._title_details[title_id]


def _chapter(chapter_id, name):
    return SimpleNamespace(chapter_id=chapter_id, name=name)


def _group(chapters):
    return SimpleNamespace(
        first_chapter_list=list(chapters),
        mid_chapter_list=[],
        last_chapter_list=[],
    )


def test_normalize_ids_requires_at_least_one_input():
    normalizer = DummyNormalizer({}, {})

    with pytest.raises(ValueError):
        normalizer._normalize_ids([], [], 0, 999)


def test_normalize_ids_uses_title_details_and_filters_by_range():
    title_details = {
        10: SimpleNamespace(chapter_list_group=[_group([_chapter(1, "#1"), _chapter(2, "#2"), _chapter(3, "Special")])])
    }
    normalizer = DummyNormalizer({}, title_details)

    result = normalizer._normalize_ids([10], [], min_chapter=1, max_chapter=2)

    assert result == {10: {1, 2}}


def test_normalize_ids_last_chapter_picks_only_final_entry():
    title_details = {
        10: SimpleNamespace(chapter_list_group=[_group([_chapter(1, "#1"), _chapter(2, "#2"), _chapter(3, "#3")])])
    }
    normalizer = DummyNormalizer({}, title_details)

    result = normalizer._normalize_ids([10], [], min_chapter=0, max_chapter=999, last_chapter=True)

    assert result == {10: {3}}


def test_normalize_ids_merges_chapter_and_title_requests():
    viewers = {
        101: SimpleNamespace(
            title_id=10,
            chapter_id=101,
            chapter_name="#1",
            chapters=[_chapter(101, "#1"), _chapter(102, "#2")],
        ),
        201: SimpleNamespace(
            title_id=20,
            chapter_id=201,
            chapter_name="#7",
            chapters=[_chapter(201, "#7")],
        ),
    }
    normalizer = DummyNormalizer(viewers, {})

    result = normalizer._normalize_ids([10], [101, 201], min_chapter=0, max_chapter=999)

    assert result == {10: {101, 102}, 20: {201}}


def test_prepare_normalized_manga_list_delegates_to_normalize_ids(monkeypatch):
    normalizer = DummyNormalizer({}, {})
    sentinel = {1: {10}}

    monkeypatch.setattr(
        normalizer,
        "_normalize_ids",
        lambda *args: sentinel,
    )

    result = normalizer._prepare_normalized_manga_list([1], [10], 0, 999, False)
    assert result is sentinel
