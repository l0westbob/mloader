"""MangaPlus auth query-parameter accessors."""

from __future__ import annotations

from mloader import config
from mloader.config import AuthSettings


def auth_params(settings: AuthSettings | None = None) -> dict[str, str]:
    """Return MangaPlus auth settings as query parameters."""
    resolved_settings = settings if settings is not None else config.AUTH_SETTINGS
    return resolved_settings.as_query_params()
