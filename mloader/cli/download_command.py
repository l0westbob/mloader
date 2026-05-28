"""Download execution CLI command behavior."""

from __future__ import annotations

import logging
from collections.abc import Callable

from mloader.application import downloads as download_use_cases
from mloader.application.errors import DownloadInterrupted, ExternalDependencyError
from mloader.application.ports import DownloadRuntimeFactory, ExporterClass
from mloader.cli.command_errors import fail
from mloader.cli.error_mapping import cli_failure_mapping, partial_download_failure_mapping
from mloader.cli.exit_codes import SUCCESS
from mloader.cli.presenter import CliPresenter
from mloader.cli.run_report import (
    Clock,
    RunIdFactory,
    new_run_id,
    summary_payload,
    utc_now,
    write_run_report_if_requested,
)
from mloader.domain.requests import DownloadRequest
from mloader.errors import SubscriptionRequiredError

log = logging.getLogger(__name__)


def run_download_request(
    request: DownloadRequest,
    *,
    presenter: CliPresenter,
    discovery_metadata: dict[str, int] | None,
    loader_factory: DownloadRuntimeFactory,
    raw_exporter: ExporterClass,
    pdf_exporter: ExporterClass,
    cbz_exporter: ExporterClass,
    write_run_report: Callable[..., None] = write_run_report_if_requested,
    run_id_factory: RunIdFactory = new_run_id,
    clock: Clock = utc_now,
) -> None:
    """Execute a prepared download request and render the final CLI result."""
    run_id = run_id_factory()
    run_started_at = clock()
    log.info("Started export")
    log.debug("Download request: %s", download_use_cases.to_chapter_id_debug_map(request))

    try:
        download_summary = download_use_cases.execute_download(
            request,
            loader_factory=loader_factory,
            raw_exporter=raw_exporter,
            pdf_exporter=pdf_exporter,
            cbz_exporter=cbz_exporter,
        )
    except DownloadInterrupted as exc:
        failure = cli_failure_mapping(exc)
        presenter.emit_download_summary(exc.summary)
        write_run_report(
            request,
            run_id=run_id,
            started_at=run_started_at,
            completed_at=clock(),
            status=failure.report_status,
            exit_code=failure.exit_code,
            discovery=discovery_metadata,
            summary=exc.summary,
            error_message="Download interrupted by user.",
        )
        fail(
            "Download interrupted by user.",
            presenter=presenter,
            exit_code=failure.exit_code,
            details={"summary": summary_payload(exc.summary)},
        )
    except SubscriptionRequiredError as exc:
        failure = cli_failure_mapping(exc)
        write_run_report(
            request,
            run_id=run_id,
            started_at=run_started_at,
            completed_at=clock(),
            status=failure.report_status,
            exit_code=failure.exit_code,
            discovery=discovery_metadata,
            summary=None,
            error_message=str(exc),
            subscription_access_failures=failure.subscription_access_failures,
        )
        fail(str(exc), presenter=presenter, exit_code=failure.exit_code)
    except ExternalDependencyError as exc:
        failure = cli_failure_mapping(exc)
        write_run_report(
            request,
            run_id=run_id,
            started_at=run_started_at,
            completed_at=clock(),
            status=failure.report_status,
            exit_code=failure.exit_code,
            discovery=discovery_metadata,
            summary=None,
            error_message=str(exc),
        )
        fail(str(exc), presenter=presenter, exit_code=failure.exit_code)
    except Exception as exc:
        failure = cli_failure_mapping(exc)
        if not presenter.json_output:
            log.exception("Failed to download manga")
        write_run_report(
            request,
            run_id=run_id,
            started_at=run_started_at,
            completed_at=clock(),
            status=failure.report_status,
            exit_code=failure.exit_code,
            discovery=discovery_metadata,
            summary=None,
            error_message=f"Download failed: {exc}",
        )
        fail("Download failed", presenter=presenter, exit_code=failure.exit_code)

    presenter.emit_download_summary(download_summary)
    resolved_summary_payload = summary_payload(download_summary)
    if download_summary.has_failures:
        failure = partial_download_failure_mapping()
        write_run_report(
            request,
            run_id=run_id,
            started_at=run_started_at,
            completed_at=clock(),
            status=failure.report_status,
            exit_code=failure.exit_code,
            discovery=discovery_metadata,
            summary=download_summary,
            error_message=f"Download completed with {download_summary.failed} failed chapter(s).",
        )
        fail(
            f"Download completed with {download_summary.failed} failed chapter(s).",
            presenter=presenter,
            exit_code=failure.exit_code,
            details={"summary": resolved_summary_payload},
        )

    log.info("SUCCESS")
    write_run_report(
        request,
        run_id=run_id,
        started_at=run_started_at,
        completed_at=clock(),
        status="ok",
        exit_code=SUCCESS,
        discovery=discovery_metadata,
        summary=download_summary,
        error_message=None,
    )
    if presenter.json_output:
        presenter.emit_json(
            {
                "status": "ok",
                "mode": "download",
                "exit_code": SUCCESS,
                "targets": {
                    "titles": len(request.titles),
                    "chapters": len(request.chapters),
                    "chapter_ids": len(request.chapter_ids),
                },
                "discovery": discovery_metadata,
                "summary": resolved_summary_payload,
            }
        )
