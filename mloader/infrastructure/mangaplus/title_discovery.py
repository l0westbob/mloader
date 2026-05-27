"""MangaPlus title-discovery gateway for ``mloader --all`` mode."""

from __future__ import annotations

from collections.abc import Sequence

from mloader.infrastructure.mangaplus import (
    browser_discovery,
    settings,
    static_discovery,
    title_index,
)

DEFAULT_LIST_PAGES = settings.DEFAULT_LIST_PAGES
DEFAULT_TITLE_INDEX_ENDPOINT = title_index.DEFAULT_TITLE_INDEX_ENDPOINT
LANGUAGE_FILTER_CHOICES = title_index.LANGUAGE_FILTER_CHOICES


class MangaPlusTitleDiscoveryGateway:
    """Concrete title-discovery gateway backed by MangaPlus API and list pages."""

    def parse_language_filters(self, languages: Sequence[str]) -> set[int] | None:
        """Map user-facing language names to MangaPlus language codes."""
        return title_index.parse_language_filters(languages)

    def collect_title_ids_from_api(
        self,
        title_index_endpoint: str,
        *,
        id_length: int | None,
        allowed_languages: set[int] | None,
        request_timeout: tuple[float, float] = settings.DEFAULT_REQUEST_TIMEOUT,
        capture_api_dir: str | None = None,
    ) -> list[int]:
        """Collect title IDs from the MangaPlus title-index API."""
        return title_index.collect_title_ids_from_api(
            title_index_endpoint,
            id_length=id_length,
            allowed_languages=allowed_languages,
            request_timeout=request_timeout,
            capture_api_dir=capture_api_dir,
        )

    def collect_title_ids(
        self,
        pages: Sequence[str],
        *,
        id_length: int | None,
        request_timeout: tuple[float, float] = settings.DEFAULT_REQUEST_TIMEOUT,
    ) -> list[int]:
        """Collect title IDs from static MangaPlus list pages."""
        return static_discovery.collect_title_ids(
            pages,
            id_length=id_length,
            request_timeout=request_timeout,
        )

    def collect_title_ids_with_browser(
        self,
        pages: Sequence[str],
        *,
        id_length: int | None,
        timeout_ms: int = 60000,
    ) -> list[int]:
        """Collect title IDs from browser-rendered MangaPlus list pages."""
        return browser_discovery.collect_title_ids_with_browser(
            pages,
            id_length=id_length,
            timeout_ms=timeout_ms,
        )


DEFAULT_GATEWAY = MangaPlusTitleDiscoveryGateway()
