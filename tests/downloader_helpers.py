"""Shared test doubles and DTO builders for downloader tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from mloader.constants import PageType
from mloader.domain.manga import Chapter, ChapterGroup, LastPage, MangaPage, MangaViewer, Title
from mloader.domain.manga import TitleDetail, ViewerPage
from mloader.domain.manga import TitleTag
from mloader.domain.planning import DownloadPlan, TitleDownloadPlan
from mloader.domain.requests import CoverFormat, EffectiveOutputFormat
from mloader.manga_loader.download_execution import (
    DownloadExecutionContext,
    DownloadExecutionService,
)
from mloader.manga_loader.download_services import DownloadServices
from mloader.manga_loader.manifest import TitleDownloadManifest
from mloader.manga_loader.page_export import PageImageService
from mloader.manga_loader.run_report import RunReport
from mloader.manga_loader.title_download import ManifestFactory
from mloader.types import ChapterLike, ExporterLike, PageIndex, ResponseLike, SessionLike, TitleLike


class DummyResponse(ResponseLike):
    """Simple HTTP response test double with status tracking."""

    def __init__(self, content: bytes = b"data") -> None:
        """Store the payload and initialize status tracking."""
        self.content = content
        self.status_checked = False

    def raise_for_status(self) -> None:
        """Record that status validation was executed."""
        self.status_checked = True


class DummySession(SessionLike):
    """Simple HTTP session test double collecting requested URLs."""

    headers: dict[str, str]

    def __init__(self, response: DummyResponse) -> None:
        """Initialize session with a fixed response object."""
        self.headers = {}
        self.response = response
        self.calls: list[str] = []
        self.adapters: dict[str, object] = {}

    def get(
        self,
        url: str,
        params: Mapping[str, object] | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> DummyResponse:
        """Record URL requests and return the configured response."""
        del params, timeout
        self.calls.append(url)
        return self.response

    def mount(self, prefix: str, adapter: object) -> None:
        """Record transport adapter configuration."""
        self.adapters[prefix] = adapter


class DummyPageImageService(PageImageService):
    """Deterministic page-image service for execution-service tests."""

    @staticmethod
    def download_image(
        session: SessionLike,
        request_timeout: tuple[float, float],
        url: str,
    ) -> bytes:
        """Return URL-derived bytes without touching network transport."""
        del session, request_timeout
        return f"img:{url}".encode("utf-8")

    @staticmethod
    def decrypt_image(
        session: SessionLike,
        request_timeout: tuple[float, float],
        url: str,
        encryption_hex: str,
    ) -> bytearray:
        """Return URL/key-derived bytes for encrypted-page tests."""
        del session, request_timeout
        return bytearray(f"dec:{url}:{encryption_hex}".encode("utf-8"))


class NullExporter:
    """Exporter test double with no filesystem side effects."""

    def add_image(self, image_data: bytes, index: PageIndex) -> None:
        """Accept image writes without side effects."""
        del image_data, index

    def skip_image(self, index: PageIndex) -> bool:
        """Return false so page processing continues by default."""
        del index
        return False

    def close(self) -> None:
        """Accept exporter finalization without side effects."""


class NullExporterFactory:
    """Exporter factory test double carrying the destination keyword payload."""

    def __init__(self, destination: str) -> None:
        """Store destination in the same shape used by concrete exporter classes."""
        self.keywords = {"destination": destination}

    def __call__(
        self,
        *,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None = None,
    ) -> ExporterLike:
        """Return a no-op exporter instance."""
        del title, chapter, next_chapter
        return NullExporter()


def _build_execution_service(
    *,
    destination: str,
    output_format: EffectiveOutputFormat = "pdf",
    meta: bool = False,
    cover: bool = False,
    cover_format: CoverFormat = "png",
    resume: bool = True,
    manifest_reset: bool = False,
    response: DummyResponse | None = None,
    manifest_factory: ManifestFactory = TitleDownloadManifest,
    services: DownloadServices | None = None,
) -> DownloadExecutionService:
    """Build a concrete execution service with deterministic test transport."""
    session = DummySession(response or DummyResponse(content=b"default"))
    return DownloadExecutionService(
        DownloadExecutionContext(
            exporter=NullExporterFactory(destination),
            destination=destination,
            output_format=output_format,
            session=session,
            request_timeout=(0.1, 0.1),
            cover=cover,
            meta=meta,
            resume=resume,
            manifest_reset=manifest_reset,
            cover_format=cover_format,
            services=services or DownloadServices.defaults(),
            prepare_download_plan=lambda *_args: DownloadPlan(title_plans=()),
            load_pages=lambda chapter_id: viewer(chapter_id=int(chapter_id)),
            clear_api_caches_for_run=lambda: None,
            clear_api_caches_for_title=lambda _title_id, _chapter_ids: None,
            manifest_factory=manifest_factory,
        )
    )


def dummy_downloader(
    destination: str = "/tmp/out",
    *,
    output_format: EffectiveOutputFormat = "pdf",
    meta: bool = False,
    cover: bool = False,
    cover_format: CoverFormat = "png",
    resume: bool = True,
    manifest_reset: bool = False,
    response: DummyResponse | None = None,
    manifest_factory: ManifestFactory = TitleDownloadManifest,
) -> DownloadExecutionService:
    """Build an execution-service harness overriding page-image side effects."""
    return _build_execution_service(
        destination=destination,
        output_format=output_format,
        meta=meta,
        cover=cover,
        cover_format=cover_format,
        resume=resume,
        manifest_reset=manifest_reset,
        response=response,
        manifest_factory=manifest_factory,
        services=replace(
            DownloadServices.defaults(),
            page_image_service=DummyPageImageService,
        ),
    )


def full_downloader(
    destination: str = "/tmp/out",
    *,
    output_format: EffectiveOutputFormat = "pdf",
    meta: bool = False,
    cover: bool = False,
    cover_format: CoverFormat = "png",
    resume: bool = True,
    manifest_reset: bool = False,
    response: DummyResponse | None = None,
    manifest_factory: ManifestFactory = TitleDownloadManifest,
) -> DownloadExecutionService:
    """Build an execution-service harness using real internals where practical."""
    return _build_execution_service(
        destination=destination,
        output_format=output_format,
        meta=meta,
        cover=cover,
        cover_format=cover_format,
        resume=resume,
        manifest_reset=manifest_reset,
        response=response,
        manifest_factory=manifest_factory,
    )


def chapter(
    chapter_id: int,
    name: str,
    sub_title: str = "sub",
    *,
    title_id: int = 10,
    thumbnail_url: str = "",
    start_timestamp: int = 0,
) -> Chapter:
    """Build a minimal chapter DTO."""
    return Chapter(
        title_id=title_id,
        chapter_id=chapter_id,
        name=name,
        sub_title=sub_title,
        thumbnail_url=thumbnail_url,
        start_timestamp=start_timestamp,
    )


def group(chapters: list[Chapter]) -> ChapterGroup:
    """Build a chapter group wrapper used by title details."""
    return ChapterGroup(
        first_chapters=tuple(chapters),
        mid_chapters=(),
        last_chapters=(),
    )


def title_detail(
    *,
    title_id: int = 10,
    name: str = "My Manga",
    author: str = "A",
    chapters: list[Chapter] | None = None,
    title_image_url: str = "",
    portrait_image_url: str = "",
    landscape_image_url: str = "",
    non_appearance_info: str = "n/a",
    number_of_views: int = 0,
    overview: str = "overview",
    tags: tuple[TitleTag, ...] = (),
    web_url: str = "",
) -> TitleDetail:
    """Build a title-detail DTO for downloader tests."""
    return TitleDetail(
        title=Title(
            title_id=title_id,
            name=name,
            author=author,
            portrait_image_url=portrait_image_url,
            landscape_image_url=landscape_image_url,
            language=0,
            overview=overview,
            tags=tags,
            web_url=web_url,
        ),
        title_image_url=title_image_url,
        overview=overview,
        non_appearance_info=non_appearance_info,
        number_of_views=number_of_views,
        chapter_groups=(group(chapters or []),),
    )


def title_plan(
    *,
    title_id: int = 10,
    name: str = "My Manga",
    author: str = "A",
    chapter_ids: set[int] | None = None,
) -> TitleDownloadPlan:
    """Build a title download plan for orchestration tests."""
    chapters = [
        chapter(chapter_id, f"#{chapter_id}", title_id=title_id)
        for chapter_id in sorted(chapter_ids or {1})
    ]
    detail = title_detail(title_id=title_id, name=name, author=author, chapters=chapters)
    return TitleDownloadPlan(title_detail=detail, selected_chapters=tuple(chapters))


def download_plan(plan: TitleDownloadPlan | None = None) -> DownloadPlan:
    """Build a one-title download plan."""
    return DownloadPlan(title_plans=(plan or title_plan(),))


def manga_page(
    image_url: str,
    *,
    page_type: PageType = PageType.SINGLE,
    encryption_key: str = "",
) -> MangaPage:
    """Build a manga-page DTO."""
    return MangaPage(
        image_url=image_url,
        width=1,
        height=1,
        page_type=page_type.value,
        encryption_key=encryption_key,
    )


def viewer(
    *,
    title_id: int = 10,
    chapter_id: int = 10,
    chapter_name: str = "#1",
    current_chapter: Chapter | None = None,
    pages: tuple[MangaPage, ...] = (),
    next_chapter: Chapter | None = None,
    include_last_page: bool = True,
) -> MangaViewer:
    """Build a manga-viewer DTO with optional downloadable pages and terminal metadata."""
    current = current_chapter or chapter(chapter_id, chapter_name, "Sub", title_id=title_id)
    viewer_pages = tuple(ViewerPage(manga_page=page, last_page=None) for page in pages)
    if include_last_page:
        viewer_pages = (
            *viewer_pages,
            ViewerPage(
                manga_page=None,
                last_page=LastPage(current_chapter=current, next_chapter=next_chapter),
            ),
        )
    return MangaViewer(
        title_id=title_id,
        chapter_id=chapter_id,
        title_name=f"Title {title_id}",
        chapter_name=chapter_name,
        chapters=(current,),
        pages=viewer_pages,
    )


def run_report() -> RunReport:
    """Return mutable run report instance matching downloader internals."""
    return RunReport()


def title_export_dir(tmp_path: Path, title_name: str = "My Manga") -> Path:
    """Return the conventional title export directory under ``tmp_path``."""
    return tmp_path / title_name
