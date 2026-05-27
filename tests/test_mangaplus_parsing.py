"""Tests for MangaPlus protobuf payload parsing into domain DTOs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mloader.errors import APIResponseError
from mloader.infrastructure.mangaplus import parsing
from mloader.response_pb2 import Response


def test_parse_manga_viewer_response() -> None:
    """Verify viewer parser maps ``success.manga_viewer`` into a domain DTO."""
    parsed = Response()
    viewer = parsed.success.manga_viewer
    viewer.title_id = 100312
    viewer.chapter_id = 1024959
    viewer.title_name = "Test Title"
    viewer.chapter_name = "#001"
    page = viewer.pages.add()
    page.manga_page.image_url = "https://img.example/page.webp"
    page.manga_page.type = 1
    last_page = viewer.pages.add()
    last_page.last_page.current_chapter.title_id = 100312
    last_page.last_page.current_chapter.chapter_id = 1024959
    last_page.last_page.current_chapter.name = "#001"
    last_page.last_page.current_chapter.sub_title = "Sub"

    result = parsing.parse_manga_viewer_response(parsed.SerializeToString())

    assert result.title_id == 100312
    assert result.chapter_id == 1024959
    assert result.downloadable_pages[0].image_url == "https://img.example/page.webp"
    assert result.last_page is not None
    assert result.last_page.current_chapter.sub_title == "Sub"


def test_parse_title_detail_response() -> None:
    """Verify title-detail parser maps ``success.title_detail_view`` into a domain DTO."""
    parsed = Response()
    title_detail = parsed.success.title_detail_view
    title_detail.title.title_id = 100312
    title_detail.title.name = "Test"
    title_detail.title.author = "Author"
    group = title_detail.chapter_list_group.add()
    chapter = group.first_chapter_list.add()
    chapter.title_id = 100312
    chapter.chapter_id = 1024959
    chapter.name = "#001"
    chapter.sub_title = "Sub"

    result = parsing.parse_title_detail_response(parsed.SerializeToString())

    assert result.title.title_id == 100312
    assert result.title.name == "Test"
    assert result.title.author == "Author"
    assert result.chapter_groups[0].first_chapters[0].chapter_id == 1024959


def test_parse_title_detail_response_maps_flat_mobile_chapter_list() -> None:
    """Verify mobile title details with flat chapters are normalized into a group."""
    parsed = Response()
    title_detail = parsed.success.title_detail_view
    title_detail.title.title_id = 100494
    title_detail.title.name = "Aliens, Baseball, and Civilization"
    chapter = title_detail.chapter_list.add()
    chapter.title_id = 100494
    chapter.chapter_id = 1024974
    chapter.name = "#001"
    chapter.sub_title = "1st Pitch"

    result = parsing.parse_title_detail_response(parsed.SerializeToString())

    assert len(result.chapter_groups) == 1
    assert result.chapter_groups[0].first_chapters[0].chapter_id == 1024974


def test_parse_manga_viewer_response_raises_for_missing_payload() -> None:
    """Verify viewer parser rejects payloads without ``success.manga_viewer``."""

    class SuccessEnvelope:
        def HasField(self, name: str) -> bool:
            return name != "manga_viewer"

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            return SimpleNamespace(success=SuccessEnvelope())

    with pytest.raises(APIResponseError, match="no manga_viewer payload"):
        parsing.parse_manga_viewer_response(b"raw", response_type=FakeResponse)


def test_raise_payload_error_classifies_empty_payload() -> None:
    """Verify empty upstream payloads are reported distinctly."""
    with pytest.raises(APIResponseError, match="empty payload") as error:
        parsing.raise_payload_error(b"", context="manga_viewer", payload_name="manga_viewer")

    assert error.value.kind == "empty"


def test_parse_title_detail_response_raises_for_missing_payload() -> None:
    """Verify title parser rejects payloads without ``success.title_detail_view``."""

    class SuccessEnvelope:
        def HasField(self, name: str) -> bool:
            return name != "title_detail_view"

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            return SimpleNamespace(success=SuccessEnvelope())

    with pytest.raises(APIResponseError, match="no title_detail_view payload"):
        parsing.parse_title_detail_response(b"raw", response_type=FakeResponse)


def test_has_message_field_handles_non_protobuf_messages() -> None:
    """Verify ``has_message_field`` returns true for objects without ``HasField``."""
    assert parsing.has_message_field(object(), "any") is True


def test_has_message_field_handles_invalid_field_name() -> None:
    """Verify ``has_message_field`` returns false when protobuf rejects field name."""

    class Message:
        def HasField(self, _name: str) -> bool:
            raise ValueError("unknown field")

    assert parsing.has_message_field(Message(), "missing") is False


def test_parse_manga_viewer_response_raises_for_missing_ids() -> None:
    """Verify viewer parser rejects payloads missing title/chapter IDs."""
    viewer = SimpleNamespace(title_id=0, chapter_id=0, pages=[SimpleNamespace()])

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            return SimpleNamespace(success=SimpleNamespace(manga_viewer=viewer))

    with pytest.raises(APIResponseError, match="without title/chapter IDs"):
        parsing.parse_manga_viewer_response(b"raw", response_type=FakeResponse)


def test_parse_manga_viewer_response_accepts_subscription_payload_without_pages() -> None:
    """Verify viewer parser lets downloader handle subscription-required empty pages."""
    viewer = SimpleNamespace(title_id=1, chapter_id=2, pages=[])

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            return SimpleNamespace(success=SimpleNamespace(manga_viewer=viewer))

    result = parsing.parse_manga_viewer_response(b"raw", response_type=FakeResponse)

    assert result.title_id == 1
    assert result.chapter_id == 2
    assert result.pages == ()


def test_parse_title_detail_response_raises_for_missing_title_identity() -> None:
    """Verify title parser rejects payloads missing title identity fields."""
    title_detail = SimpleNamespace(
        title=SimpleNamespace(title_id=0, name=""),
        chapter_list_group=[
            SimpleNamespace(
                first_chapter_list=[SimpleNamespace()],
                mid_chapter_list=[],
                last_chapter_list=[],
            )
        ],
    )

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            return SimpleNamespace(success=SimpleNamespace(title_detail_view=title_detail))

    with pytest.raises(APIResponseError, match="without title identity"):
        parsing.parse_title_detail_response(b"raw", response_type=FakeResponse)


def test_parse_title_detail_response_raises_for_missing_groups() -> None:
    """Verify title parser rejects payloads with no chapter groups."""
    title_detail = SimpleNamespace(
        title=SimpleNamespace(title_id=1, name="T"),
        chapter_list_group=[],
    )

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            return SimpleNamespace(success=SimpleNamespace(title_detail_view=title_detail))

    with pytest.raises(APIResponseError, match="without chapter groups"):
        parsing.parse_title_detail_response(b"raw", response_type=FakeResponse)


def test_parse_title_detail_response_raises_for_missing_entries() -> None:
    """Verify title parser rejects groups that contain no chapters."""
    title_detail = SimpleNamespace(
        title=SimpleNamespace(title_id=1, name="T"),
        chapter_list_group=[
            SimpleNamespace(first_chapter_list=[], mid_chapter_list=[], last_chapter_list=[])
        ],
    )

    class FakeResponse:
        @staticmethod
        def FromString(_content: bytes) -> SimpleNamespace:
            return SimpleNamespace(success=SimpleNamespace(title_detail_view=title_detail))

    with pytest.raises(APIResponseError, match="without chapter entries"):
        parsing.parse_title_detail_response(b"raw", response_type=FakeResponse)
