"""Default dependency bindings for CLI command behavior."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast

from mloader.application.ports import TitleDiscoveryGateway
from mloader.cli import capture_command, discovery_command
from mloader.cli.presenter import CliPresenter
from mloader.cli.run_report import write_run_report_if_requested as write_run_report
from mloader.domain.requests import DownloadRequest, DownloadSummary
from mloader.infrastructure.mangaplus import title_discovery
from mloader.infrastructure.mangaplus.capture_verify import (
    CaptureVerificationSummary,
    verify_capture_schema,
    verify_capture_schema_against_baseline,
)


def write_run_report_if_requested(
    request: DownloadRequest,
    *,
    run_id: str,
    started_at: datetime,
    status: str,
    exit_code: int,
    discovery: dict[str, int] | None,
    summary: DownloadSummary | None,
    error_message: str | None,
    subscription_access_failures: int = 0,
    completed_at: datetime | None = None,
) -> None:
    """Write a run report using the production filesystem adapter."""
    write_run_report(
        request,
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        exit_code=exit_code,
        discovery=discovery,
        summary=summary,
        error_message=error_message,
        subscription_access_failures=subscription_access_failures,
        path_type=Path,
    )


def run_capture_verification_mode(
    *,
    verify_capture_schema_dir: str,
    verify_capture_baseline_dir: str | None,
    presenter: CliPresenter,
) -> CaptureVerificationSummary:
    """Run capture verification using the production verifier functions."""
    return capture_command.run_capture_verification_mode(
        verify_capture_schema_dir=verify_capture_schema_dir,
        verify_capture_baseline_dir=verify_capture_baseline_dir,
        presenter=presenter,
        verify_capture_schema_func=verify_capture_schema,
        verify_capture_schema_against_baseline_func=verify_capture_schema_against_baseline,
    )


def resolve_all_mode_targets(
    *,
    request: DownloadRequest,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    browser_fallback: bool,
    list_only: bool,
    presenter: CliPresenter,
) -> tuple[DownloadRequest | None, dict[str, int] | None]:
    """Resolve ``--all`` targets using the production title-discovery gateway."""
    return discovery_command.resolve_all_mode_targets(
        request=request,
        pages=pages,
        title_index_endpoint=title_index_endpoint,
        id_length=id_length,
        languages=languages,
        browser_fallback=browser_fallback,
        list_only=list_only,
        presenter=presenter,
        discovery_gateway=cast(TitleDiscoveryGateway, title_discovery.DEFAULT_GATEWAY),
    )
