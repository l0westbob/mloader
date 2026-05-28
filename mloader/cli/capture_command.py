"""Capture-verification CLI command behavior."""

from __future__ import annotations

from collections.abc import Callable

from mloader.cli.command_errors import fail
from mloader.cli.exit_codes import VALIDATION_ERROR
from mloader.cli.presenter import CliPresenter
from mloader.infrastructure.mangaplus.capture_verify import (
    CaptureVerificationError,
    CaptureVerificationSummary,
)


def run_capture_verification_mode(
    *,
    verify_capture_schema_dir: str,
    verify_capture_baseline_dir: str | None,
    presenter: CliPresenter,
    verify_capture_schema_func: Callable[[str], CaptureVerificationSummary],
    verify_capture_schema_against_baseline_func: Callable[[str, str], CaptureVerificationSummary],
) -> CaptureVerificationSummary:
    """Run capture schema verification command mode and return summary."""
    try:
        if verify_capture_baseline_dir:
            summary = verify_capture_schema_against_baseline_func(
                verify_capture_schema_dir,
                verify_capture_baseline_dir,
            )
        else:
            summary = verify_capture_schema_func(verify_capture_schema_dir)
    except CaptureVerificationError as exc:
        fail(str(exc), presenter=presenter, exit_code=VALIDATION_ERROR)

    return summary
