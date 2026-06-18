"""Shared typed fakes for CLI and application download tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import requests

from mloader.domain.requests import (
    CoverFormat,
    DownloadSummary,
    EffectiveOutputFormat,
    FilenameStyle,
)
from mloader.errors import APIResponseError, DownloadInterruptedError, SubscriptionRequiredError
from mloader.types import ChapterLike, ExporterFactoryLike, ExporterLike, PageIndex, TitleLike

DEFAULT_FAILED_CHAPTER_IDS = (102300, 102301)
DEFAULT_INTERRUPTED_CHAPTER_ID = 102278


@dataclass(frozen=True)
class FakeTitle:
    """Minimal title value satisfying exporter factory tests."""

    name: str = "Title"
    author: str = "Author"
    portrait_image_url: str = ""
    landscape_image_url: str = ""
    language: int = 0


@dataclass(frozen=True)
class FakeChapter:
    """Minimal chapter value satisfying exporter factory tests."""

    chapter_id: int = 1
    name: str = "#1"
    sub_title: str = ""
    thumbnail_url: str = ""


class RecordingExporter(ExporterLike):
    """Exporter test double that records constructor payloads."""

    init_args: ClassVar[dict[str, object] | None] = None
    calls: ClassVar[list[dict[str, object]]] = []

    @classmethod
    def reset(cls) -> None:
        """Reset captured constructor state."""
        cls.init_args = None
        cls.calls = []

    def __init__(
        self,
        *,
        destination: str,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
        add_language_to_chapter_name: bool = True,
    ) -> None:
        """Record exporter constructor arguments."""
        payload: dict[str, object] = {
            "destination": destination,
            "title": title,
            "chapter": chapter,
            "next_chapter": next_chapter,
            "add_chapter_title": add_chapter_title,
            "add_chapter_subdir": add_chapter_subdir,
            "add_language_to_chapter_name": add_language_to_chapter_name,
        }
        type(self).init_args = payload
        type(self).calls.append(payload)

    def add_image(self, image_data: bytes, index: PageIndex) -> None:
        """Accept image writes without side effects."""
        del image_data, index

    def skip_image(self, index: PageIndex) -> bool:
        """Return false so page processing would continue."""
        del index
        return False

    def close(self) -> None:
        """Accept exporter finalization without side effects."""


class RecordingRawExporter(RecordingExporter):
    """Raw exporter marker for output-selection tests."""


class RecordingPdfExporter(RecordingExporter):
    """PDF exporter marker for output-selection tests."""


class RecordingCbzExporter(RecordingExporter):
    """CBZ exporter marker for output-selection tests."""


class RecordingDownloadRuntime:
    """Download runtime test double capturing constructor and download calls."""

    init_args: ClassVar[dict[str, object] | None] = None
    download_args: ClassVar[dict[str, object] | None] = None
    summary: ClassVar[DownloadSummary | None] = DownloadSummary(
        downloaded=1,
        skipped_manifest=0,
        failed=0,
        failed_chapter_ids=(),
    )

    @classmethod
    def reset(cls) -> None:
        """Reset captured runtime state."""
        cls.init_args = None
        cls.download_args = None

    def __init__(
        self,
        exporter: ExporterFactoryLike,
        quality: str,
        split: bool,
        meta: bool,
        cover: bool = False,
        *,
        destination: str = "mloader_downloads",
        output_format: EffectiveOutputFormat = "cbz",
        capture_api_dir: str | None = None,
        filename_style: FilenameStyle = "legacy",
        rename_existing_filenames: bool = False,
        resume: bool = True,
        manifest_reset: bool = False,
        cover_format: CoverFormat = "png",
    ) -> None:
        """Record initialization arguments for assertions."""
        type(self).init_args = {
            "exporter_factory": exporter,
            "quality": quality,
            "split": split,
            "meta": meta,
            "cover": cover,
            "cover_format": cover_format,
            "destination": destination,
            "output_format": output_format,
            "capture_api_dir": capture_api_dir,
            "filename_style": filename_style,
            "rename_existing_filenames": rename_existing_filenames,
            "resume": resume,
            "manifest_reset": manifest_reset,
        }

    def download(
        self,
        *,
        title_ids: set[int] | frozenset[int] | None = None,
        chapter_numbers: set[int] | frozenset[int] | None = None,
        chapter_ids: set[int] | frozenset[int] | None = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> DownloadSummary | None:
        """Record download call keyword arguments for assertions."""
        type(self).download_args = {
            "title_ids": title_ids,
            "chapter_numbers": chapter_numbers,
            "chapter_ids": chapter_ids,
            "min_chapter": min_chapter,
            "max_chapter": max_chapter,
            "last_chapter": last_chapter,
        }
        return type(self).summary


class ApplicationRecordingDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double preserving application use-case summary expectations."""

    summary: ClassVar[DownloadSummary | None] = DownloadSummary(
        downloaded=2,
        skipped_manifest=1,
        failed=0,
        failed_chapter_ids=(),
    )


class RuntimeFailingDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double that raises a generic failure."""

    def download(self, **kwargs: object) -> DownloadSummary | None:
        """Raise a runtime error to exercise CLI exception handling."""
        del kwargs
        raise RuntimeError("boom")


class SubscriptionRequiredDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double that raises a subscription-required error."""

    message: ClassVar[str] = "A MAX subscription is required to download this chapter."

    def download(self, **kwargs: object) -> DownloadSummary | None:
        """Raise a subscription-required error to test CLI messaging."""
        del kwargs
        raise SubscriptionRequiredError(type(self).message)


class ShortSubscriptionRequiredDownloadRuntime(SubscriptionRequiredDownloadRuntime):
    """Runtime double using the concise subscription message expected by discovery tests."""

    message: ClassVar[str] = "subscription required"


class RequestErrorDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double that raises request-layer failures."""

    def download(self, **kwargs: object) -> DownloadSummary | None:
        """Raise request exception to verify external-failure mapping."""
        del kwargs
        raise requests.RequestException("network down")


class PartialFailureDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double returning a failed chapter summary."""

    summary: ClassVar[DownloadSummary | None] = DownloadSummary(
        downloaded=2,
        skipped_manifest=1,
        failed=2,
        failed_chapter_ids=DEFAULT_FAILED_CHAPTER_IDS,
    )


class SinglePartialFailureDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double returning one failed chapter summary for discovery mode tests."""

    summary: ClassVar[DownloadSummary | None] = DownloadSummary(
        downloaded=1,
        skipped_manifest=0,
        failed=1,
        failed_chapter_ids=(123,),
    )


class InterruptedDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double raising interrupt wrapper with partial summary."""

    interrupted_summary: ClassVar[DownloadSummary] = DownloadSummary(
        downloaded=1,
        skipped_manifest=1,
        failed=1,
        failed_chapter_ids=(DEFAULT_INTERRUPTED_CHAPTER_ID,),
    )

    def download(self, **kwargs: object) -> DownloadSummary | None:
        """Raise downloader interrupt error containing partial run summary."""
        del kwargs
        raise DownloadInterruptedError(type(self).interrupted_summary)


class APIResponseErrorDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double that raises MangaPlus payload validation errors."""

    def download(self, **kwargs: object) -> DownloadSummary | None:
        """Raise APIResponseError for application external-dependency mapping tests."""
        del kwargs
        raise APIResponseError("MangaPlus API returned no manga_viewer payload.")


class RequestFailingDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double that raises a generic request error for application tests."""

    def download(self, **kwargs: object) -> DownloadSummary | None:
        """Raise request exception for external-dependency mapping tests."""
        del kwargs
        raise requests.RequestException("network")


class ApplicationInterruptedDownloadRuntime(InterruptedDownloadRuntime):
    """Runtime double raising the application-level interrupted summary."""

    interrupted_summary: ClassVar[DownloadSummary] = DownloadSummary(
        downloaded=3,
        skipped_manifest=1,
        failed=1,
        failed_chapter_ids=(77,),
    )


class NoneReturningDownloadRuntime(RecordingDownloadRuntime):
    """Runtime double returning no summary."""

    summary: ClassVar[DownloadSummary | None] = None
