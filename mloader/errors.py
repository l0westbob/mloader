"""Domain-specific exceptions raised by mloader runtime components."""

from __future__ import annotations

from typing import Literal

from mloader.domain.requests import DownloadSummary

ApiErrorKind = Literal[
    "http",
    "network",
    "api_error",
    "subscription_required",
    "empty",
    "unknown",
]
FailureKind = Literal[
    "validation",
    "external_dependency",
    "subscription_required",
    "interrupted",
    "internal_bug",
]


class MLoaderError(Exception):
    """Base exception for mloader-specific runtime failures."""

    error_kind: FailureKind = "internal_bug"


class SubscriptionRequiredError(MLoaderError):
    """Raised when a chapter requires a subscription unavailable to the caller."""

    error_kind: FailureKind = "subscription_required"


class DownloadInterruptedError(MLoaderError):
    """Raised when a download run is interrupted by user signal."""

    error_kind: FailureKind = "interrupted"

    def __init__(self, summary: DownloadSummary) -> None:
        """Store partial run summary for CLI reporting."""
        super().__init__("Download interrupted by user.")
        self.summary = summary


class APIResponseError(MLoaderError):
    """Raised when MangaPlus API returns an invalid or non-success payload."""

    error_kind: FailureKind = "external_dependency"

    def __init__(
        self,
        message: str,
        *,
        kind: ApiErrorKind = "unknown",
        code: str | None = None,
    ) -> None:
        """Store a machine-readable API failure classification."""
        super().__init__(message)
        self.kind = kind
        self.api_error_kind = kind
        self.code = code
