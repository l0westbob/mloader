"""Application use cases for title discovery."""

from __future__ import annotations

from collections.abc import Collection

import requests

from mloader.application.errors import DiscoveryError
from mloader.application.ports import TitleDiscoveryGateway
from mloader.domain.requests import DiscoveryRequest
from mloader.errors import APIResponseError


def discover_title_ids(
    request: DiscoveryRequest,
    *,
    gateway: TitleDiscoveryGateway,
) -> tuple[list[int], list[str]]:
    """Discover title IDs and return ``(ids, notices)`` for CLI output."""
    notices: list[str] = []
    allowed_languages = gateway.parse_language_filters(request.languages)
    title_ids: list[int] = []

    try:
        title_ids = gateway.collect_title_ids_from_api(
            request.title_index_endpoint,
            id_length=request.id_length,
            allowed_languages=allowed_languages,
            capture_api_dir=request.capture_api_dir,
        )
    except requests.RequestException as exc:
        if allowed_languages is not None:
            raise DiscoveryError(
                "Language filtering requires API title-index access, but the API request failed: "
                f"{exc}"
            ) from exc
        notices.append(f"API title-index fetch failed: {exc}")
    except APIResponseError as exc:
        if allowed_languages is not None:
            raise DiscoveryError(
                "Language filtering requires API title-index access, but the API response "
                f"was unusable: {exc}"
            ) from exc
        notices.append(f"API title-index payload unusable: {exc}")

    if not title_ids and allowed_languages is None:
        try:
            title_ids = gateway.collect_title_ids(
                request.pages,
                id_length=request.id_length,
            )
        except requests.RequestException as exc:
            if not request.browser_fallback:
                raise DiscoveryError(f"Failed to fetch title pages: {exc}") from exc
            notices.append(f"Static fetch failed: {exc}. Retrying with browser fallback.")

    if not title_ids and request.browser_fallback and allowed_languages is None:
        try:
            title_ids = gateway.collect_title_ids_with_browser(
                request.pages,
                id_length=request.id_length,
            )
        except RuntimeError as exc:
            raise DiscoveryError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive fallback wrapper
            raise DiscoveryError(f"Browser fallback failed: {exc}") from exc

    if not title_ids and allowed_languages is not None:
        selected_languages = ", ".join(language.lower() for language in request.languages)
        raise DiscoveryError(
            f"No title IDs found for selected language filter(s): {selected_languages}."
        )

    if not title_ids:
        raise DiscoveryError(
            "No title IDs found on configured list pages. "
            "Try enabling browser fallback or verify page access."
        )

    return title_ids, notices


def summarize_discovery(title_ids: Collection[int]) -> str:
    """Return human-readable summary for discovered title IDs."""
    return f"Discovered {len(title_ids)} title ID(s)."


def format_discovered_ids(title_ids: Collection[int]) -> str:
    """Return a space-separated title ID list for CLI printing."""
    return " ".join(str(title_id) for title_id in title_ids)


def verify_discovery_flags(
    *,
    download_all_titles: bool,
    list_only: bool,
    languages: Collection[str],
) -> str | None:
    """Return validation error message for discovery-only flags, if any."""
    if list_only and not download_all_titles:
        return "--list-only requires --all."
    if languages and not download_all_titles:
        return "--language requires --all."
    return None
