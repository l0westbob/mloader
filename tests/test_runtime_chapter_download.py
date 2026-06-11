"""Tests for chapter-level download orchestration."""

from __future__ import annotations

from typing import Any

import pytest

from mloader.domain.manga import MangaPage
from mloader.domain.manga import TitleTag
from mloader.errors import SubscriptionRequiredError
from mloader.manga_loader.chapter_download import ChapterDownloader
from mloader.manga_loader.filename_policy import FilenamePolicy
from mloader.types import ChapterLike, ExporterLike, PageIndex, TitleLike
from tests.downloader_helpers import (
    NullExporterFactory,
    chapter as _chapter,
    manga_page as _manga_page,
    title_detail as _title_detail,
    viewer as _viewer,
)


class NoopManifest:
    """Manifest double implementing the runtime manifest protocol."""

    def reset(self) -> None:
        """No-op reset."""

    def flush(self) -> None:
        """No-op flush."""

    def is_completed(self, chapter_id: int) -> bool:
        """Treat every chapter as incomplete."""
        del chapter_id
        return False

    def mark_started(
        self,
        chapter_id: int,
        *,
        chapter_name: str,
        sub_title: str,
        output_format: str,
    ) -> None:
        """No-op start marker."""
        del chapter_id, chapter_name, sub_title, output_format

    def mark_completed(self, chapter_id: int, *, output_path: str | None = None) -> None:
        """No-op completion marker."""
        del chapter_id, output_path

    def mark_failed(self, chapter_id: int, *, error: str) -> None:
        """No-op failure marker."""
        del chapter_id, error


class FixedExporterFactory:
    """Exporter factory double returning one prebuilt exporter."""

    def __init__(self, exporter: ExporterLike) -> None:
        """Store the exporter instance returned for each factory call."""
        self.exporter = exporter

    def __call__(
        self,
        *,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None = None,
    ) -> ExporterLike:
        """Return the configured exporter instance."""
        del title, chapter, next_chapter
        return self.exporter


def test_process_chapter_raises_when_subscription_required() -> None:
    """Verify chapter downloader raises subscription error without last_page payload."""
    viewer = _viewer(chapter_name="C1", include_last_page=False)

    with pytest.raises(SubscriptionRequiredError):
        ChapterDownloader.process_chapter(
            viewer=viewer,
            title=_title_detail(name="t").title,
            chapter_index=1,
            total_chapters=1,
            chapter_id=10,
            output_format="pdf",
            manifest=None,
            exporter_factory=NullExporterFactory("unused"),
            process_pages=lambda *_args: None,
            prepare_filename=FilenamePolicy.prepare_filename,
        )


def test_process_chapter_creates_exporter_and_closes() -> None:
    """Verify chapter downloader builds exporter, processes pages, and closes exporter."""

    class ExporterInstance:
        """Exporter test double with close tracking."""

        def __init__(self) -> None:
            """Initialize close tracking state."""
            self.closed = False

        def close(self) -> None:
            """Record close invocation."""
            self.closed = True

        def add_image(self, image_data: bytes, index: PageIndex) -> None:
            """Accept image writes without side effects."""
            del image_data, index

        def skip_image(self, index: PageIndex) -> bool:
            """Return false so processing continues."""
            del index
            return False

    instance = ExporterInstance()
    captured: dict[str, Any] = {}
    started: list[tuple[int, str, str, str]] = []
    completed: list[tuple[int, str | None]] = []

    class Manifest(NoopManifest):
        def mark_started(
            self,
            chapter_id: int,
            *,
            chapter_name: str,
            sub_title: str,
            output_format: str,
        ) -> None:
            started.append((chapter_id, chapter_name, sub_title, output_format))

        def mark_completed(self, chapter_id: int, *, output_path: str | None = None) -> None:
            completed.append((chapter_id, output_path))

    class ExporterFactory:
        """Capture exporter constructor arguments and return test instance."""

        def __call__(
            self,
            *,
            title: TitleLike,
            chapter: ChapterLike,
            next_chapter: ChapterLike | None = None,
        ) -> ExporterLike:
            captured.update({"title": title, "chapter": chapter, "next_chapter": next_chapter})
            return instance

    processed: list[tuple[tuple[MangaPage, ...], str, ExporterLike]] = []
    current_chapter = _chapter(10, "#1", "Sub/Raw", start_timestamp=1747407600)
    viewer = _viewer(
        chapter_id=10,
        chapter_name="#1",
        current_chapter=current_chapter,
        pages=(_manga_page("u1"),),
    )

    title_detail = _title_detail(
        name="My Manga",
        overview="Summary",
        tags=(TitleTag(name="Action", slug="action"),),
        web_url="https://example.invalid/title",
    )
    ChapterDownloader.process_chapter(
        viewer=viewer,
        title=title_detail.title,
        chapter_index=1,
        total_chapters=1,
        chapter_id=10,
        output_format="pdf",
        manifest=Manifest(),
        exporter_factory=ExporterFactory(),
        process_pages=lambda pages, chapter_name, exporter: processed.append(
            (pages, chapter_name, exporter)
        ),
        prepare_filename=FilenamePolicy.prepare_filename,
    )

    assert captured["title"] is title_detail.title
    assert captured["title"].overview == "Summary"
    assert captured["title"].tags[0].name == "Action"
    assert captured["title"].web_url == "https://example.invalid/title"
    assert captured["chapter"].sub_title == "Sub Raw"
    assert captured["chapter"].start_timestamp == 1747407600
    assert current_chapter.sub_title == "Sub/Raw"
    assert captured["next_chapter"] is None
    assert processed[0][1] == "#1"
    assert len(processed[0][0]) == 1
    assert instance.closed is True
    assert started == [(10, "#1", "Sub Raw", "pdf")]
    assert completed == [(10, None)]


def test_process_chapter_marks_manifest_failed_when_page_processing_raises() -> None:
    """Verify chapter export-processing failures are raised to title-level handling."""
    discarded: list[bool] = []

    class Exporter:
        def add_image(self, image_data: bytes, index: PageIndex) -> None:
            """Accept image writes without side effects."""
            del image_data, index

        def skip_image(self, index: PageIndex) -> bool:
            """Return false so processing continues."""
            del index
            return False

        def close(self) -> None:
            """No-op close used by this failure-path test."""

        def discard(self) -> None:
            """Record cleanup when export processing fails."""
            discarded.append(True)

    viewer = _viewer(
        chapter_id=10,
        chapter_name="#1",
        current_chapter=_chapter(10, "#1", "Sub"),
        pages=(_manga_page("u1"),),
    )

    with pytest.raises(RuntimeError, match="boom"):
        ChapterDownloader.process_chapter(
            viewer=viewer,
            title=_title_detail(name="My Manga").title,
            chapter_index=1,
            total_chapters=1,
            chapter_id=10,
            output_format="pdf",
            manifest=NoopManifest(),
            exporter_factory=FixedExporterFactory(Exporter()),
            process_pages=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
            prepare_filename=FilenamePolicy.prepare_filename,
        )

    assert discarded == [True]


def test_process_chapter_raises_when_no_downloadable_pages() -> None:
    """Verify chapter download fails when viewer payload has no downloadable image pages."""
    started: list[int] = []
    completed: list[int] = []

    class Exporter:
        def add_image(self, image_data: bytes, index: PageIndex) -> None:
            """Accept image writes without side effects."""
            del image_data, index

        def skip_image(self, index: PageIndex) -> bool:
            """Return false so processing continues."""
            del index
            return False

        def close(self) -> None:
            """No-op close for no-pages path."""

    class Manifest(NoopManifest):
        def mark_started(
            self,
            chapter_id: int,
            *,
            chapter_name: str,
            sub_title: str,
            output_format: str,
        ) -> None:
            del chapter_name, sub_title, output_format
            started.append(chapter_id)

        def mark_completed(self, chapter_id: int, *, output_path: str | None = None) -> None:
            del output_path
            completed.append(chapter_id)

    viewer = _viewer(
        chapter_id=10,
        chapter_name="#1",
        current_chapter=_chapter(10, "#1", "Sub"),
        pages=(),
    )

    with pytest.raises(RuntimeError, match="no downloadable pages"):
        ChapterDownloader.process_chapter(
            viewer=viewer,
            title=_title_detail(name="My Manga").title,
            chapter_index=1,
            total_chapters=1,
            chapter_id=10,
            output_format="pdf",
            manifest=Manifest(),
            exporter_factory=FixedExporterFactory(Exporter()),
            process_pages=lambda *_args: None,
            prepare_filename=FilenamePolicy.prepare_filename,
        )

    assert started == [10]
    assert completed == []
