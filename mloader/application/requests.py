"""Application request-model construction."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

from mloader.domain.requests import (
    ApiOutputFormat,
    COVER_FORMATS,
    CoverFormat,
    DownloadRequest,
    DiscoveryRequest,
)


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
    cover: bool,
    cover_format: str,
    resume: bool,
    manifest_reset: bool,
    chapters: Collection[int] | None,
    chapter_ids: Collection[int] | None,
    titles: Collection[int] | None,
    run_report_path: str | None = None,
) -> DownloadRequest:
    """Create a typed download request from CLI-normalized values."""
    api_output_format: ApiOutputFormat = "pdf" if output_format == "pdf" else "cbz"
    normalized_cover_format = cover_format.lower()
    if normalized_cover_format not in COVER_FORMATS:
        raise ValueError(f"Unsupported cover format: {cover_format}")
    typed_cover_format = cast(CoverFormat, normalized_cover_format)
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
        cover=cover,
        cover_format=typed_cover_format,
        resume=resume,
        manifest_reset=manifest_reset,
        chapters=frozenset(chapters or set()),
        chapter_ids=frozenset(chapter_ids or set()),
        titles=frozenset(titles or set()),
        run_report_path=run_report_path,
    )


def build_discovery_request(
    *,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    browser_fallback: bool,
    capture_api_dir: str | None = None,
) -> DiscoveryRequest:
    """Create a typed discovery request from CLI-normalized values."""
    return DiscoveryRequest(
        pages=pages,
        title_index_endpoint=title_index_endpoint,
        id_length=id_length,
        languages=languages,
        browser_fallback=browser_fallback,
        capture_api_dir=capture_api_dir,
    )
