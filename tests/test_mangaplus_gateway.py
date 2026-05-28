"""Tests for the MangaPlus HTTP gateway adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from mloader.errors import APIResponseError
from mloader.infrastructure.mangaplus import gateway
from mloader.infrastructure.mangaplus import parsing
from mloader.response_pb2 import Response
from mloader.types import SessionLike
from tests.http_fakes import BytesResponse


class DummySession(SessionLike):
    """HTTP session test double for gateway requests."""

    def __init__(self) -> None:
        """Initialize request recording state."""
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.mounted: list[tuple[str, object]] = []

    def mount(self, prefix: str, adapter: object) -> None:
        """Record mounted adapters."""
        self.mounted.append((prefix, adapter))

    def get(
        self,
        url: str,
        params: Mapping[str, object] | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> BytesResponse:
        """Return protobuf payloads based on requested endpoint."""
        del timeout
        self.calls.append((url, dict(params) if params is not None else None))
        params = params or {}
        if url.endswith("/api/title_detailV3"):
            return BytesResponse(_title_detail_payload(int(str(params["title_id"]))))
        if url.endswith("/api/manga_viewer"):
            return BytesResponse(_viewer_payload(int(str(params["chapter_id"]))))
        raise AssertionError(f"Unexpected URL: {url}")


class Capture:
    """Payload capture test double."""

    def __init__(self) -> None:
        """Initialize capture record storage."""
        self.records: list[dict[str, Any]] = []

    def capture(self, **kwargs: Any) -> None:
        """Store capture call keyword arguments."""
        self.records.append(kwargs)


def _title_detail_payload(title_id: int) -> bytes:
    """Build a title-detail protobuf payload."""
    response = Response()
    title_detail = response.success.title_detail_view
    title_detail.title.title_id = title_id
    title_detail.title.name = f"Title {title_id}"
    chapter = title_detail.chapter_list_group.add().first_chapter_list.add()
    chapter.title_id = title_id
    chapter.chapter_id = title_id + 1000
    chapter.name = "#001"
    chapter.sub_title = "Sub"
    return response.SerializeToString()


def _viewer_payload(chapter_id: int) -> bytes:
    """Build a manga-viewer protobuf payload."""
    response = Response()
    viewer = response.success.manga_viewer
    viewer.title_id = 100010
    viewer.chapter_id = chapter_id
    viewer.chapter_name = "#001"
    page = viewer.pages.add()
    page.manga_page.image_url = "https://img.example/page.webp"
    last_page = viewer.pages.add()
    last_page.last_page.current_chapter.title_id = 100010
    last_page.last_page.current_chapter.chapter_id = chapter_id
    last_page.last_page.current_chapter.name = "#001"
    return response.SerializeToString()


def test_gateway_fetches_caches_captures_and_evicts_payloads() -> None:
    """Verify gateway transport, caching, capture, and eviction behavior."""
    session = DummySession()
    capture = Capture()
    client = gateway.MangaPlusGateway(
        session=session,
        api_base_url="https://api.example",
        quality="low",
        split=False,
        payload_capture=capture,
        auth_params_provider=lambda: {"secret": "token"},
        title_cache_max_size=1,
        viewer_cache_max_size=1,
    )

    first_title = client.get_title_details(100010)
    cached_title = client.get_title_details(100010)
    second_title = client.get_title_details(100011)
    first_viewer = client.load_pages(1000311)
    cached_viewer = client.load_pages(1000311)
    client.clear_title_caches(100010, None)

    assert first_title is cached_title
    assert second_title.title.title_id == 100011
    assert first_viewer is cached_viewer
    assert session.headers["User-Agent"] == "okhttp/4.12.0"
    assert len(session.calls) == 3
    assert len(capture.records) == 3
    assert capture.records[0]["params"]["secret"] == "token"


def test_gateway_parse_manga_viewer_reports_payload_errors() -> None:
    """Verify gateway viewer parser reports missing payload and identity errors."""
    missing_payload = Response()
    missing_payload.success.title_detail_view.title.title_id = 100010
    missing_payload.success.title_detail_view.title.name = "Other"

    with pytest.raises(APIResponseError, match="no manga_viewer payload"):
        parsing.parse_manga_viewer_response(missing_payload.SerializeToString())

    missing_identity = Response()
    missing_identity.success.manga_viewer.title_name = "Viewer without IDs"

    with pytest.raises(APIResponseError, match="without title/chapter IDs"):
        parsing.parse_manga_viewer_response(missing_identity.SerializeToString())


def test_gateway_parse_title_detail_reports_payload_errors() -> None:
    """Verify gateway title parser reports missing payload and invalid title details."""
    missing_payload = Response()
    missing_payload.success.manga_viewer.title_id = 100010
    missing_payload.success.manga_viewer.chapter_id = 1000311

    with pytest.raises(APIResponseError, match="no title_detail_view payload"):
        parsing.parse_title_detail_response(missing_payload.SerializeToString())

    missing_identity = Response()
    missing_identity.success.title_detail_view.overview = "missing identity"
    missing_identity.success.title_detail_view.chapter_list_group.add().first_chapter_list.add()

    with pytest.raises(APIResponseError, match="without title identity"):
        parsing.parse_title_detail_response(missing_identity.SerializeToString())

    missing_groups = Response()
    missing_groups.success.title_detail_view.title.title_id = 100010
    missing_groups.success.title_detail_view.title.name = "No groups"

    with pytest.raises(APIResponseError, match="without chapter groups"):
        parsing.parse_title_detail_response(missing_groups.SerializeToString())

    missing_entries = Response()
    missing_entries.success.title_detail_view.title.title_id = 100010
    missing_entries.success.title_detail_view.title.name = "No entries"
    missing_entries.success.title_detail_view.chapter_list_group.add()

    with pytest.raises(APIResponseError, match="without chapter entries"):
        parsing.parse_title_detail_response(missing_entries.SerializeToString())
