"""Application-layer workflows decoupled from CLI parsing details."""

from __future__ import annotations

from functools import partial
from typing import Callable, Collection, Mapping, Protocol, Sequence, TypeAlias, cast

import requests

from mloader.domain.requests import (
    ApiOutputFormat,
    DownloadSummary,
    DownloadRequest,
    DiscoveryRequest,
    EffectiveOutputFormat,
)
from mloader.errors import APIResponseError
from mloader.manga_loader.downloader import DownloadInterruptedError
from mloader.manga_loader.init import MangaLoader
from mloader.types import ExporterFactoryLike


class WorkflowError(RuntimeError):
    """Base class for workflow-level execution failures."""


class DiscoveryError(WorkflowError):
    """Raise when title discovery for ``--all`` cannot produce IDs."""


class ExternalDependencyError(WorkflowError):
    """Raise when external systems fail during download execution."""


class DownloadInterrupted(ExternalDependencyError):
    """Raise when user interrupts download while preserving partial summary."""

    def __init__(self, summary: DownloadSummary) -> None:
        """Store partial summary generated before interruption."""
        super().__init__("Download interrupted by user.")
        self.summary = summary


class TitleDiscoveryGateway(Protocol):
    """Protocol for title discovery backends used by ``--all`` workflow."""

    def parse_language_filters(self, languages: Sequence[str]) -> set[int] | None:
        """Map user-facing language names to API language codes."""

    def collect_title_ids_from_api(
        self,
        title_index_endpoint: str,
        *,
        id_length: int | None,
        allowed_languages: set[int] | None,
        request_timeout: tuple[float, float] = (5.0, 30.0),
    ) -> list[int]:
        """Collect title IDs from the allV2 API endpoint."""

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


ExporterClass: TypeAlias = Callable[..., object]


def discover_title_ids(
    request: DiscoveryRequest,
    *,
    gateway: TitleDiscoveryGateway,
) -> tuple[list[int], list[str]]:
    """Discover title IDs and return ``(ids, notices)`` for CLI output."""
    notices: list[str] = []
    allowed_languages = gateway.parse_language_filters(request.languages)
    title_ids: list[int] = []

    try:
        title_ids = gateway.collect_title_ids_from_api(
            request.title_index_endpoint,
            id_length=request.id_length,
            allowed_languages=allowed_languages,
        )
    except requests.RequestException as exc:
        if allowed_languages is not None:
            raise DiscoveryError(
                "Language filtering requires API title-index access, but the API request failed: "
                f"{exc}"
            ) from exc
        notices.append(f"API title-index fetch failed: {exc}")

    if not title_ids and allowed_languages is None:
        try:
            title_ids = gateway.collect_title_ids(
                request.pages,
                id_length=request.id_length,
            )
        except requests.RequestException as exc:
            if not request.browser_fallback:
                raise DiscoveryError(f"Failed to fetch title pages: {exc}") from exc
            notices.append(f"Static fetch failed: {exc}. Retrying with browser fallback.")

    if not title_ids and request.browser_fallback and allowed_languages is None:
        try:
            title_ids = gateway.collect_title_ids_with_browser(
                request.pages,
                id_length=request.id_length,
            )
        except RuntimeError as exc:
            raise DiscoveryError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive fallback wrapper
            raise DiscoveryError(f"Browser fallback failed: {exc}") from exc

    if not title_ids and allowed_languages is not None:
        selected_languages = ", ".join(language.lower() for language in request.languages)
        raise DiscoveryError(f"No title IDs found for selected language filter(s): {selected_languages}.")

    if not title_ids:
        raise DiscoveryError(
            "No title IDs found on configured list pages. "
            "Try enabling browser fallback or verify page access."
        )

    return title_ids, notices


def resolve_exporter(
    request: DownloadRequest,
    *,
    raw_exporter: ExporterClass,
    pdf_exporter: ExporterClass,
    cbz_exporter: ExporterClass,
) -> tuple[ExporterClass, EffectiveOutputFormat]:
    """Resolve exporter class and effective output format from request options."""
    if request.raw:
        return raw_exporter, "raw"
    if request.output_format == "pdf":
        return pdf_exporter, "pdf"
    return cbz_exporter, "cbz"


def execute_download(
    request: DownloadRequest,
    *,
    loader_factory: type[MangaLoader],
    raw_exporter: ExporterClass,
    pdf_exporter: ExporterClass,
    cbz_exporter: ExporterClass,
) -> DownloadSummary:
    """Execute the configured download request via the provided factories."""
    exporter_class, effective_output_format = resolve_exporter(
        request,
        raw_exporter=raw_exporter,
        pdf_exporter=pdf_exporter,
        cbz_exporter=cbz_exporter,
    )
    typed_exporter_factory = cast(
        ExporterFactoryLike,
        cast(
            object,
            partial(
                exporter_class,
                destination=request.out_dir,
                add_chapter_title=request.chapter_title,
                add_chapter_subdir=request.chapter_subdir,
            ),
        ),
    )

    loader = loader_factory(
        typed_exporter_factory,
        request.quality,
        request.split,
        request.meta,
        destination=request.out_dir,
        output_format=effective_output_format,
        capture_api_dir=request.capture_api_dir,
        resume=request.resume,
        manifest_reset=request.manifest_reset,
    )
    try:
        summary = loader.download(
            title_ids=request.titles or None,
            chapter_numbers=request.chapters or None,
            chapter_ids=request.chapter_ids or None,
            min_chapter=request.begin,
            max_chapter=request.max_chapter,
            last_chapter=request.last,
        )
    except DownloadInterruptedError as exc:
        raise DownloadInterrupted(exc.summary) from exc
    except (requests.RequestException, APIResponseError) as exc:
        raise ExternalDependencyError(f"Download request failed: {exc}") from exc

    if isinstance(summary, DownloadSummary):
        return summary
    return DownloadSummary(
        downloaded=0,
        skipped_manifest=0,
        failed=0,
        failed_chapter_ids=(),
    )


def summarize_discovery(title_ids: Collection[int]) -> str:
    """Return human-readable summary for discovered title IDs."""
    return f"Discovered {len(title_ids)} title ID(s)."


def format_discovered_ids(title_ids: Collection[int]) -> str:
    """Return a space-separated title ID list for CLI printing."""
    return " ".join(str(title_id) for title_id in title_ids)


def verify_discovery_flags(
    *,
    download_all_titles: bool,
    list_only: bool,
    languages: Collection[str],
) -> str | None:
    """Return validation error message for discovery-only flags, if any."""
    if list_only and not download_all_titles:
        return "--list-only requires --all."
    if languages and not download_all_titles:
        return "--language requires --all."
    return None


def build_download_request(
    *,
    out_dir: str,
    raw: bool,
    output_format: str,
    capture_api_dir: str | None,
    quality: str,
    split: bool,
    begin: int,
    end: int | None,
    last: bool,
    chapter_title: bool,
    chapter_subdir: bool,
    meta: bool,
    resume: bool,
    manifest_reset: bool,
    chapters: Collection[int] | None,
    chapter_ids: Collection[int] | None,
    titles: Collection[int] | None,
) -> DownloadRequest:
    """Create a typed download request from CLI-normalized values."""
    api_output_format: ApiOutputFormat = "pdf" if output_format == "pdf" else "cbz"
    return DownloadRequest(
        out_dir=out_dir,
        raw=raw,
        output_format=api_output_format,
        capture_api_dir=capture_api_dir,
        quality=quality,
        split=split,
        begin=begin,
        end=end,
        last=last,
        chapter_title=chapter_title,
        chapter_subdir=chapter_subdir,
        meta=meta,
        resume=resume,
        manifest_reset=manifest_reset,
        chapters=frozenset(chapters or set()),
        chapter_ids=frozenset(chapter_ids or set()),
        titles=frozenset(titles or set()),
    )


def build_discovery_request(
    *,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    browser_fallback: bool,
) -> DiscoveryRequest:
    """Create a typed discovery request from CLI-normalized values."""
    return DiscoveryRequest(
        pages=pages,
        title_index_endpoint=title_index_endpoint,
        id_length=id_length,
        languages=languages,
        browser_fallback=browser_fallback,
    )


def to_chapter_id_debug_map(
    request: DownloadRequest,
) -> Mapping[str, int | bool | str | None]:
    """Return minimal structured fields useful for debug logging."""
    return {
        "target_titles": len(request.titles),
        "target_chapters": len(request.chapters),
        "target_chapter_ids": len(request.chapter_ids),
        "begin": request.begin,
        "end": request.end,
        "raw": request.raw,
        "format": request.output_format,
        "resume": request.resume,
        "manifest_reset": request.manifest_reset,
    }
