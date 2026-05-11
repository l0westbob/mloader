"""Domain-specific exceptions raised by mloader runtime components."""

from __future__ import annotations

from typing import Literal

ApiErrorKind = Literal[
    "http",
    "network",
    "api_error",
    "subscription_required",
    "empty",
    "unknown",
]


class MLoaderError(Exception):
    """Base exception for mloader-specific runtime failures."""


class SubscriptionRequiredError(MLoaderError):
    """Raised when a chapter requires a subscription unavailable to the caller."""


class APIResponseError(MLoaderError):
    """Raised when MangaPlus API returns an invalid or non-success payload."""

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
        self.code = code
