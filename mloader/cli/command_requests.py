"""Translate Click-normalized CLI options into application request models."""

from __future__ import annotations

from collections.abc import Collection

import click
from click.core import ParameterSource

from mloader.application import discovery as discovery_use_cases
from mloader.application import requests as app_requests
from mloader.domain.requests import DownloadRequest, DiscoveryRequest


def parameter_was_provided(ctx: click.Context, parameter_name: str) -> bool:
    """Return whether a Click parameter was provided explicitly on the command line."""
    return ctx.get_parameter_source(parameter_name) is ParameterSource.COMMANDLINE


def build_download_request(
    ctx: click.Context,
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
    filename_style: str = "legacy",
    rename_existing_filenames: bool = False,
    resume: bool,
    manifest_reset: bool,
    chapters: Collection[int] | None,
    chapter_ids: Collection[int] | None,
    titles: Collection[int] | None,
    run_report_path: str | None,
) -> DownloadRequest:
    """Build a download request from CLI options while preserving CLI-specific semantics."""
    cover_enabled = cover or parameter_was_provided(ctx, "cover_format")
    return app_requests.build_download_request(
        out_dir=out_dir,
        raw=raw,
        output_format=output_format,
        capture_api_dir=capture_api_dir,
        quality=quality,
        split=split,
        begin=begin,
        end=end,
        last=last,
        chapter_title=chapter_title,
        chapter_subdir=chapter_subdir,
        meta=meta,
        cover=cover_enabled,
        cover_format=cover_format,
        filename_style=filename_style,
        rename_existing_filenames=rename_existing_filenames,
        resume=resume,
        manifest_reset=manifest_reset,
        chapters=chapters,
        chapter_ids=chapter_ids,
        titles=titles,
        run_report_path=run_report_path,
    )


def validate_discovery_flags(
    *,
    download_all_titles: bool,
    list_only: bool,
    languages: Collection[str],
) -> str | None:
    """Validate discovery-only flag combinations from CLI options."""
    return discovery_use_cases.verify_discovery_flags(
        download_all_titles=download_all_titles,
        list_only=list_only,
        languages=languages,
    )


def build_discovery_request(
    *,
    request: DownloadRequest,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    browser_fallback: bool,
) -> DiscoveryRequest:
    """Build a discovery request from CLI options and the active download request."""
    return app_requests.build_discovery_request(
        pages=pages,
        title_index_endpoint=title_index_endpoint,
        id_length=id_length,
        languages=languages,
        browser_fallback=browser_fallback,
        capture_api_dir=request.capture_api_dir,
    )
