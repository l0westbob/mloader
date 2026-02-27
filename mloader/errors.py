"""Domain-specific exceptions raised by mloader runtime components."""

from __future__ import annotations


class MLoaderError(Exception):
    """Base exception for mloader-specific runtime failures."""


class SubscriptionRequiredError(MLoaderError):
    """Raised when a chapter requires a subscription unavailable to the caller."""


class APIResponseError(MLoaderError):
    """Raised when MangaPlus API returns an invalid or non-success payload."""
