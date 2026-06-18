"""Compose loader runtime services into the concrete ``MangaLoader`` facade."""

from __future__ import annotations

from typing import Literal

from mloader.domain.requests import CoverFormat, DownloadSummary, FilenameStyle
from mloader.infrastructure.mangaplus.settings import (
    DEFAULT_API_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRIES,
)
from mloader.types import ExporterFactoryLike, PayloadCaptureLike, SessionLike

from .download_services import DownloadServices
from .runner import DownloadRunner


class MangaLoader:
    """Facade object exposing the current programmatic download API."""

    def __init__(
        self,
        exporter: ExporterFactoryLike,
        quality: str,
        split: bool,
        meta: bool,
        cover: bool = False,
        destination: str = "mloader_downloads",
        output_format: Literal["raw", "cbz", "pdf"] = "cbz",
        session: SessionLike | None = None,
        api_url: str = DEFAULT_API_BASE_URL,
        request_timeout: tuple[float, float] = DEFAULT_REQUEST_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        capture_api_dir: str | None = None,
        filename_style: FilenameStyle = "legacy",
        rename_existing_filenames: bool = False,
        resume: bool = True,
        manifest_reset: bool = False,
        services: DownloadServices | None = None,
        cover_format: CoverFormat = "png",
    ) -> None:
        """Initialize the composed runtime for the current public constructor surface."""
        self._runtime = DownloadRunner(
            exporter=exporter,
            quality=quality,
            split=split,
            meta=meta,
            cover=cover,
            cover_format=cover_format,
            destination=destination,
            output_format=output_format,
            session=session,
            api_url=api_url,
            request_timeout=request_timeout,
            retries=retries,
            capture_api_dir=capture_api_dir,
            filename_style=filename_style,
            rename_existing_filenames=rename_existing_filenames,
            resume=resume,
            manifest_reset=manifest_reset,
            services=services or DownloadServices.defaults(),
        )

    @property
    def session(self) -> SessionLike:
        """Expose active HTTP session for tests and runtime introspection."""
        return self._runtime.session

    @property
    def destination(self) -> str:
        """Expose configured destination directory."""
        return self._runtime.destination

    @property
    def output_format(self) -> Literal["raw", "cbz", "pdf"]:
        """Expose configured chapter output format."""
        return self._runtime.output_format

    @property
    def request_timeout(self) -> tuple[float, float]:
        """Expose configured request timeout tuple."""
        return self._runtime.request_timeout

    @property
    def payload_capture(self) -> PayloadCaptureLike | None:
        """Expose payload capture backend when capture mode is enabled."""
        return self._runtime.payload_capture

    def download(
        self,
        *,
        title_ids: set[int] | frozenset[int] | None = None,
        chapter_numbers: set[int] | frozenset[int] | None = None,
        chapter_ids: set[int] | frozenset[int] | None = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> DownloadSummary:
        """Delegate download orchestration to the composed runtime."""
        return self._runtime.download(
            title_ids=title_ids,
            chapter_numbers=chapter_numbers,
            chapter_ids=chapter_ids,
            min_chapter=min_chapter,
            max_chapter=max_chapter,
            last_chapter=last_chapter,
        )
