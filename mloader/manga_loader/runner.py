"""Concrete download runtime behind the public ``MangaLoader`` facade."""

from __future__ import annotations

from collections.abc import Collection
from typing import Literal

from mloader.domain.manga import MangaViewer, TitleDetail
from mloader.domain.planning import DownloadPlan, build_download_plan
from mloader.domain.requests import CoverFormat, DownloadSummary
from mloader.infrastructure.mangaplus.capture import APIPayloadCapture
from mloader.infrastructure.mangaplus.gateway import MangaPlusGateway
from mloader.manga_loader.download_execution import (
    DownloadExecutionContext,
    DownloadExecutionService,
)
from mloader.manga_loader.download_services import DownloadServices
from mloader.types import ExporterFactoryLike, PayloadCaptureLike, SessionLike


class DownloadRunner:
    """Composition root for MangaPlus gateway access and download execution."""

    def __init__(
        self,
        exporter: ExporterFactoryLike,
        quality: str,
        split: bool,
        meta: bool,
        cover: bool,
        cover_format: CoverFormat,
        destination: str,
        output_format: Literal["raw", "cbz", "pdf"],
        session: SessionLike | None,
        api_url: str,
        request_timeout: tuple[float, float],
        retries: int,
        capture_api_dir: str | None,
        resume: bool,
        manifest_reset: bool,
        services: DownloadServices,
    ) -> None:
        """Initialize gateway, capture, and execution service dependencies."""
        self.meta = meta
        self.cover = cover
        self.cover_format = cover_format
        self.exporter = exporter
        self.destination = destination
        self.output_format = output_format
        self.quality = quality
        self.split = split
        self.request_timeout = request_timeout
        self.resume = resume
        self.manifest_reset = manifest_reset
        self.services = services
        self.payload_capture: PayloadCaptureLike | None = (
            APIPayloadCapture(capture_api_dir) if capture_api_dir else None
        )
        self.gateway = MangaPlusGateway(
            session=session,
            api_base_url=api_url,
            quality=quality,
            split=split,
            request_timeout=request_timeout,
            retries=retries,
            payload_capture=self.payload_capture,
        )
        self.session = self.gateway.session
        self._api_url = self.gateway.api_base_url

    def download(
        self,
        *,
        title_ids: Collection[int] | None = None,
        chapter_numbers: Collection[int] | None = None,
        chapter_ids: Collection[int] | None = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> DownloadSummary:
        """Start a download run using already validated filters."""
        return self._execution_service().download(
            title_ids=title_ids,
            chapter_numbers=chapter_numbers,
            chapter_ids=chapter_ids,
            min_chapter=min_chapter,
            max_chapter=max_chapter,
            last_chapter=last_chapter,
        )

    def _execution_service(self) -> DownloadExecutionService:
        """Build a download execution service for current runtime settings."""
        return DownloadExecutionService(
            DownloadExecutionContext(
                destination=self.destination,
                output_format=self.output_format,
                exporter=self.exporter,
                session=self.session,
                request_timeout=self.request_timeout,
                cover=self.cover,
                meta=self.meta,
                resume=self.resume,
                manifest_reset=self.manifest_reset,
                cover_format=self.cover_format,
                services=self.services,
                prepare_download_plan=self._prepare_download_plan,
                load_pages=self._load_pages,
                clear_api_caches_for_run=self._clear_api_caches_for_run,
                clear_api_caches_for_title=self._clear_api_caches_for_title,
            )
        )

    def _prepare_download_plan(
        self,
        title_ids: Collection[int] | None,
        chapter_numbers: Collection[int] | None,
        chapter_ids: Collection[int] | None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool,
    ) -> DownloadPlan:
        """Resolve title/chapter filters into a concrete domain download plan."""
        return build_download_plan(
            title_ids=title_ids,
            chapter_numbers=chapter_numbers,
            chapter_ids=chapter_ids,
            min_chapter=min_chapter,
            max_chapter=max_chapter,
            last_chapter=last_chapter,
            load_title_detail=lambda title_id: self._get_title_details(title_id),
            load_viewer=lambda chapter_id: self._load_pages(chapter_id),
        )

    def _get_title_details(self, title_id: str | int) -> TitleDetail:
        """Load title details through the MangaPlus gateway."""
        return self.gateway.get_title_details(title_id)

    def _load_pages(self, chapter_id: str | int) -> MangaViewer:
        """Load chapter viewer data through the MangaPlus gateway."""
        return self.gateway.load_pages(chapter_id)

    def _clear_api_caches_for_run(self) -> None:
        """Clear all cached gateway payloads for a download run."""
        self.gateway.clear_run_caches()

    def _clear_api_caches_for_title(
        self,
        title_id: int,
        chapter_ids: Collection[int] | None,
    ) -> None:
        """Clear title-scoped gateway cache entries after title processing."""
        self.gateway.clear_title_caches(title_id, chapter_ids)
