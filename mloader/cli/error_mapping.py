"""Map typed runtime/application failures to CLI/report behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mloader.cli.exit_codes import EXTERNAL_FAILURE, INTERNAL_BUG
from mloader.errors import FailureKind

ReportStatus = Literal["error"]


@dataclass(frozen=True, slots=True)
class CliFailureMapping:
    """CLI boundary mapping for a normalized failure kind."""

    error_kind: FailureKind
    exit_code: int
    report_status: ReportStatus = "error"
    subscription_access_failures: int = 0


def cli_failure_mapping(error: BaseException) -> CliFailureMapping:
    """Return CLI/report behavior for ``error`` based on its failure kind."""
    error_kind = getattr(error, "error_kind", "internal_bug")
    if error_kind == "subscription_required":
        return CliFailureMapping(
            error_kind="subscription_required",
            exit_code=EXTERNAL_FAILURE,
            subscription_access_failures=1,
        )
    if error_kind in {"external_dependency", "interrupted"}:
        return CliFailureMapping(error_kind=error_kind, exit_code=EXTERNAL_FAILURE)
    return CliFailureMapping(error_kind="internal_bug", exit_code=INTERNAL_BUG)


def partial_download_failure_mapping() -> CliFailureMapping:
    """Return CLI/report behavior for completed runs with failed chapters."""
    return CliFailureMapping(error_kind="external_dependency", exit_code=EXTERNAL_FAILURE)
