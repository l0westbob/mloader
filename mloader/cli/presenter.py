"""CLI presentation helpers for human and JSON output modes."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

import click

from mloader.application import workflows
from mloader.domain.requests import DownloadSummary
from mloader.manga_loader.capture_verify import CaptureVerificationSummary


class CliPresenter:
    """Render command outputs for human and machine-readable modes."""

    def __init__(self, *, json_output: bool, quiet: bool) -> None:
        """Store output-mode flags for rendering decisions."""
        self.json_output = json_output
        self.quiet = quiet

    @property
    def emits_human_output(self) -> bool:
        """Return whether human-readable output should be emitted."""
        return not self.json_output and not self.quiet

    def emit_intro(self, intro: str) -> None:
        """Emit a styled intro banner when human output is enabled."""
        if self.emits_human_output:
            click.echo(click.style(intro, fg="blue"))

    def emit_notice(self, message: str) -> None:
        """Emit one human-readable informational message."""
        if self.emits_human_output:
            click.echo(message)

    def emit_notices(self, messages: Iterable[str]) -> None:
        """Emit multiple human-readable informational messages."""
        for message in messages:
            self.emit_notice(message)

    def emit_capture_verification(
        self,
        *,
        summary: CaptureVerificationSummary,
        capture_dir: str,
        baseline_dir: str | None,
    ) -> None:
        """Emit capture-verification output in current render mode."""
        if self.json_output:
            self.emit_json(
                {
                    "status": "ok",
                    "mode": "verify_capture",
                    "exit_code": 0,
                    "capture_dir": capture_dir,
                    "baseline_dir": baseline_dir,
                    "total_records": summary.total_records,
                    "endpoint_counts": dict(sorted(summary.endpoint_counts.items())),
                }
            )
            return

        if not self.emits_human_output:
            return

        endpoint_overview = ", ".join(
            f"{name}={count}" for name, count in sorted(summary.endpoint_counts.items())
        )
        if baseline_dir:
            click.echo(
                f"Verified {summary.total_records} capture payload(s) in {capture_dir} "
                f"against baseline {baseline_dir} ({endpoint_overview})"
            )
        else:
            click.echo(
                f"Verified {summary.total_records} capture payload(s) in "
                f"{capture_dir} ({endpoint_overview})"
            )

    def emit_discovery_summary(self, title_ids: list[int]) -> None:
        """Emit discovered title count in human mode."""
        self.emit_notice(workflows.summarize_discovery(title_ids))

    def emit_discovery_ids(self, title_ids: list[int]) -> None:
        """Emit discovered title IDs in human mode."""
        self.emit_notice(workflows.format_discovered_ids(title_ids))

    def emit_download_summary(self, summary: DownloadSummary) -> None:
        """Emit human-readable download result counters."""
        if not self.emits_human_output:
            return
        click.echo(
            "Download summary: "
            f"downloaded={summary.downloaded}, "
            f"skipped_manifest={summary.skipped_manifest}, "
            f"failed={summary.failed}"
        )
        if summary.failed_chapter_ids:
            failed_ids = " ".join(str(chapter_id) for chapter_id in summary.failed_chapter_ids)
            click.echo(f"Failed chapter IDs: {failed_ids}")

    def emit_json(self, payload: Mapping[str, Any]) -> None:
        """Emit one machine-readable JSON object to stdout."""
        click.echo(json.dumps(payload, sort_keys=True))
