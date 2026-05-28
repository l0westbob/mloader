"""Unit tests for application title-discovery use cases."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from mloader.application import discovery
from mloader.application.errors import DiscoveryError
from mloader.application.ports import TitleDiscoveryGateway
from mloader.application.requests import build_discovery_request
from mloader.errors import APIResponseError


def test_verify_discovery_flags_rejects_list_only_without_all() -> None:
    """Verify list-only validation fails when all-mode is disabled."""
    message = discovery.verify_discovery_flags(
        download_all_titles=False,
        list_only=True,
        languages=(),
    )

    assert message == "--list-only requires --all."


def test_verify_discovery_flags_rejects_language_without_all() -> None:
    """Verify language validation fails when all-mode is disabled."""
    message = discovery.verify_discovery_flags(
        download_all_titles=False,
        list_only=False,
        languages=("english",),
    )

    assert message == "--language requires --all."


def test_verify_discovery_flags_accepts_all_mode() -> None:
    """Verify discovery flag validation allows all-mode combinations."""
    message = discovery.verify_discovery_flags(
        download_all_titles=True,
        list_only=True,
        languages=("english",),
    )

    assert message is None


def test_discover_title_ids_requires_usable_api_payload_for_language_filters() -> None:
    """Verify language-filter discovery stops on API payload/schema errors."""

    class PayloadErrorGateway(TitleDiscoveryGateway):
        def parse_language_filters(self, languages: Sequence[str]) -> set[int] | None:
            del languages
            return {0}

        def collect_title_ids_from_api(
            self,
            title_index_endpoint: str,
            *,
            id_length: int | None,
            allowed_languages: set[int] | None,
            request_timeout: tuple[float, float] = (5.0, 30.0),
            capture_api_dir: str | None = None,
        ) -> list[int]:
            del (
                title_index_endpoint,
                id_length,
                allowed_languages,
                request_timeout,
                capture_api_dir,
            )
            raise APIResponseError("schema drift", kind="unknown")

        def collect_title_ids(
            self,
            pages: Sequence[str],
            *,
            id_length: int | None,
            request_timeout: tuple[float, float] = (5.0, 30.0),
        ) -> list[int]:
            del pages, id_length, request_timeout
            raise AssertionError("static fallback must not run with language filters")

        def collect_title_ids_with_browser(
            self,
            pages: Sequence[str],
            *,
            id_length: int | None,
            timeout_ms: int = 60000,
        ) -> list[int]:
            del pages, id_length, timeout_ms
            raise AssertionError("browser fallback must not run with language filters")

    request = build_discovery_request(
        pages=("https://example.com",),
        title_index_endpoint="https://api.example/allV2",
        id_length=6,
        languages=("english",),
        browser_fallback=True,
    )

    with pytest.raises(DiscoveryError, match="API response was unusable"):
        discovery.discover_title_ids(
            request,
            gateway=PayloadErrorGateway(),
        )


def test_format_helpers_return_expected_cli_strings() -> None:
    """Verify helper formatters produce deterministic human-facing output."""
    assert discovery.summarize_discovery([1, 2, 3]) == "Discovered 3 title ID(s)."
    assert discovery.format_discovered_ids([100001, 100002]) == "100001 100002"
