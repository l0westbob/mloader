"""Application-layer errors shared by CLI use cases."""

from __future__ import annotations

from mloader.domain.requests import DownloadSummary
from mloader.errors import FailureKind


class ApplicationError(RuntimeError):
    """Base class for application-level execution failures."""

    error_kind: FailureKind = "internal_bug"


class DiscoveryError(ApplicationError):
    """Raised when title discovery for ``--all`` cannot produce IDs."""

    error_kind: FailureKind = "external_dependency"


class ExternalDependencyError(ApplicationError):
    """Raised when external systems fail during download execution."""

    error_kind: FailureKind = "external_dependency"


class DownloadInterrupted(ExternalDependencyError):
    """Raised when user interrupts download while preserving partial summary."""

    error_kind: FailureKind = "interrupted"

    def __init__(self, summary: DownloadSummary) -> None:
        """Store partial summary generated before interruption."""
        super().__init__("Download interrupted by user.")
        self.summary = summary
