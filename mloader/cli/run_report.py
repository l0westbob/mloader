"""Run-report helpers for CLI command execution."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from mloader.application import downloads as download_use_cases
from mloader.domain.requests import DownloadRequest, DownloadSummary

log = logging.getLogger(__name__)

Clock = Callable[[], datetime]
RunIdFactory = Callable[[], str]


def utc_now() -> datetime:
    """Return the current UTC timestamp for report metadata."""
    return datetime.now(timezone.utc)


def new_run_id() -> str:
    """Return a new opaque run identifier."""
    return uuid4().hex


def summary_payload(summary: DownloadSummary) -> dict[str, object]:
    """Build JSON-serializable summary payload from immutable summary model."""
    return {
        "downloaded": summary.downloaded,
        "skipped_manifest": summary.skipped_manifest,
        "failed": summary.failed,
        "failed_chapter_ids": list(summary.failed_chapter_ids),
    }


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
    clock: Clock = utc_now,
    path_type: type[Path] = Path,
) -> None:
    """Write an optional JSON run report without changing CLI success semantics."""
    if not request.run_report_path:
        return

    resolved_completed_at = completed_at or clock()
    resolved_summary_payload = (
        summary_payload(summary)
        if summary is not None
        else {
            "downloaded": 0,
            "skipped_manifest": 0,
            "failed": 0,
            "failed_chapter_ids": [],
        }
    )
    report: dict[str, object] = {
        "run_id": run_id,
        "status": status,
        "exit_code": exit_code,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": resolved_completed_at.isoformat(),
        "duration_seconds": round((resolved_completed_at - started_at).total_seconds(), 3),
        "selected_args": {
            **download_use_cases.to_chapter_id_debug_map(request),
            "out_dir": request.out_dir,
            "quality": request.quality,
            "split": request.split,
        },
        "discovery": {
            "discovered_title_count": (discovery or {}).get("discovered_titles", 0),
        },
        "summary": resolved_summary_payload,
        "subscription_access_failures": subscription_access_failures,
        "exporter_safety": {
            "mode": "disk-backed-tempfiles",
            "version": "pdf-streaming-and-atomic-cbz-v1",
        },
    }
    if error_message:
        report["error"] = error_message

    report_path = path_type(request.run_report_path)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        log.warning("Failed to write run report: %s", report_path, exc_info=True)
