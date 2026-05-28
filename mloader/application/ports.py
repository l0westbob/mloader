"""Application-layer ports for runtime and infrastructure adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from mloader.domain.requests import CoverFormat, DownloadSummary, EffectiveOutputFormat
from mloader.types import ChapterLike, ExporterFactoryLike, ExporterLike, TitleLike


class ExporterClass(Protocol):
    """Port for exporter classes selected by application output options."""

    def __call__(
        self,
        *,
        destination: str,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
    ) -> ExporterLike:
        """Create an exporter instance for one chapter."""


class TitleDiscoveryGateway(Protocol):
    """Port for title discovery backends used by the ``--all`` command."""

    def parse_language_filters(self, languages: Sequence[str]) -> set[int] | None:
        """Map user-facing language names to API language codes."""

    def collect_title_ids_from_api(
        self,
        title_index_endpoint: str,
        *,
        id_length: int | None,
        allowed_languages: set[int] | None,
        request_timeout: tuple[float, float] = (5.0, 30.0),
        capture_api_dir: str | None = None,
    ) -> list[int]:
        """Collect title IDs from the title-index API endpoint."""

    def collect_title_ids(
        self,
        pages: Sequence[str],
        *,
        id_length: int | None,
        request_timeout: tuple[float, float] = (5.0, 30.0),
    ) -> list[int]:
        """Collect title IDs from static page HTML."""

    def collect_title_ids_with_browser(
        self,
        pages: Sequence[str],
        *,
        id_length: int | None,
        timeout_ms: int = 60000,
    ) -> list[int]:
        """Collect title IDs from browser-rendered list pages."""


class DownloadRuntime(Protocol):
    """Port for an executable download runtime."""

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
        """Execute one download run and return a summary when available."""


class DownloadRuntimeFactory(Protocol):
    """Port for constructing download runtimes from application options."""

    def __call__(
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
        resume: bool = True,
        manifest_reset: bool = False,
        cover_format: CoverFormat = "png",
    ) -> DownloadRuntime:
        """Build a runtime capable of executing a download request."""
