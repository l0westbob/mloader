"""Tests for page download, decryption, and export behavior."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import click
import pytest

from mloader.constants import PageType
from mloader.manga_loader.page_export import PageExportService, PageImageService
from mloader.types import ExporterLike, PageIndex
from tests.downloader_helpers import (
    DummyResponse,
    DummySession,
    manga_page as _manga_page,
)


def test_process_chapter_pages_handles_double_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify DOUBLE page types are converted into ranged page indexes."""

    @contextmanager
    def fake_progressbar(items: list[Any], **kwargs: Any) -> Iterator[list[Any]]:
        """Yield given items without rendering a real progress bar."""
        del kwargs
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    calls: list[tuple[bytes, Any]] = []

    class FakeExporter(ExporterLike):
        """Exporter test double recording add_image calls."""

        def skip_image(self, index: PageIndex) -> bool:
            """Never skip images in this test exporter."""
            del index
            return False

        def add_image(self, image_data: bytes, index: PageIndex) -> None:
            """Record blob and page index for assertions."""
            calls.append((image_data, index))

        def close(self) -> None:
            """Accept exporter finalization without side effects."""

    pages = [
        _manga_page("u1", page_type=PageType.DOUBLE),
        _manga_page("u2", page_type=PageType.SINGLE),
    ]

    PageExportService.export_pages(
        pages,
        chapter_name="#1",
        exporter=FakeExporter(),
        fetch_page_image=lambda page: f"img:{page.image_url}".encode("utf-8"),
    )

    assert calls[0][0] == b"img:u1"
    assert calls[0][1] == range(0, 1)
    assert calls[1][0] == b"img:u2"
    assert calls[1][1] == 2


def test_download_image_calls_raise_for_status() -> None:
    """Verify image downloads call response.raise_for_status before returning bytes."""
    response = DummyResponse(content=b"img")
    session = DummySession(response)

    result = PageImageService.download_image(session, (0.1, 0.1), "http://img")

    assert session.calls == ["http://img"]
    assert response.status_checked is True
    assert result == b"img"


def test_process_chapter_pages_skips_when_exporter_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify page export skips add_image when exporter says to skip."""

    @contextmanager
    def fake_progressbar(items: list[Any], **kwargs: Any) -> Iterator[list[Any]]:
        """Yield given items without rendering a real progress bar."""
        del kwargs
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    class SkipExporter(ExporterLike):
        """Exporter test double that always skips images."""

        def skip_image(self, index: PageIndex) -> bool:
            """Return True for every page index."""
            del index
            return True

        def add_image(self, image_data: bytes, index: PageIndex) -> None:
            """Fail test if add_image is called while skip_image is True."""
            del image_data, index
            raise AssertionError("add_image should not be called when skip_image is True")

        def close(self) -> None:
            """Accept exporter finalization without side effects."""

    pages = [_manga_page("u1", page_type=PageType.SINGLE)]
    PageExportService.export_pages(
        pages,
        chapter_name="#1",
        exporter=SkipExporter(),
        fetch_page_image=lambda _page: b"unused",
    )


def test_process_chapter_pages_uses_decrypt_for_encrypted_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify encrypted pages route through decrypt path before export."""

    @contextmanager
    def fake_progressbar(items: list[Any], **kwargs: Any) -> Iterator[list[Any]]:
        """Yield given items without rendering a real progress bar."""
        del kwargs
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    captured: list[bytes] = []

    class CapturingExporter(ExporterLike):
        """Exporter test double collecting written image bytes."""

        def skip_image(self, index: PageIndex) -> bool:
            """Never skip pages in this test."""
            del index
            return False

        def add_image(self, image_data: bytes, index: PageIndex) -> None:
            """Store output image blobs for assertion."""
            del index
            captured.append(image_data)

        def close(self) -> None:
            """Accept exporter finalization without side effects."""

    pages = [
        _manga_page("u1", page_type=PageType.SINGLE, encryption_key="abcd"),
        _manga_page("u2", page_type=PageType.SINGLE, encryption_key=""),
    ]
    PageExportService.export_pages(
        pages,
        chapter_name="#1",
        exporter=CapturingExporter(),
        fetch_page_image=lambda page: PageImageService.fetch_page_image(
            page,
            download_image=lambda url: f"img:{url}".encode("utf-8"),
            decrypt_image=lambda url, key: bytearray(f"dec:{url}:{key}".encode("utf-8")),
        ),
    )

    assert captured == [b"dec:u1:abcd", b"img:u2"]


def test_page_image_service_decrypts_encrypted_payload() -> None:
    """Verify page-image service owns encrypted-image download and decryption."""
    response = DummyResponse(content=bytes([0x40]))
    session = DummySession(response)

    assert PageImageService.decrypt_image(session, (0.1, 0.1), "http://img", "01") == bytearray(
        [0x41]
    )
    assert session.calls == ["http://img"]
    assert response.status_checked is True
