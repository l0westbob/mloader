"""Tests for ``mloader --all`` CLI orchestration."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
import requests
from click.testing import CliRunner

from mloader.cli.exit_codes import EXTERNAL_FAILURE, VALIDATION_ERROR
from mloader.cli import main as cli_main
from mloader.errors import APIResponseError
from tests.cli_fakes import (
    RecordingDownloadRuntime,
    RuntimeFailingDownloadRuntime,
    ShortSubscriptionRequiredDownloadRuntime,
    SinglePartialFailureDownloadRuntime,
)


def _patch_discovery_gateway(
    monkeypatch: pytest.MonkeyPatch,
    *,
    api: Any | None = None,
    static: Any | None = None,
    browser: Any | None = None,
) -> None:
    """Patch production discovery gateway methods for CLI orchestration tests."""
    gateway = cli_main.title_discovery.DEFAULT_GATEWAY
    if api is not None:
        monkeypatch.setattr(gateway, "collect_title_ids_from_api", api)
    if static is not None:
        monkeypatch.setattr(gateway, "collect_title_ids", static)
    if browser is not None:
        monkeypatch.setattr(gateway, "collect_title_ids_with_browser", browser)


def test_cli_list_only_prints_ids_without_downloading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --all --list-only prints IDs and exits before loader initialization."""
    RecordingDownloadRuntime.init_args = None
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001, 100002],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--list-only"])

    assert result.exit_code == 0
    assert "100001 100002" in result.output
    assert RecordingDownloadRuntime.init_args is None


def test_cli_rejects_list_only_without_all() -> None:
    """Verify --list-only requires --all mode."""
    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--list-only"])

    assert result.exit_code == VALIDATION_ERROR
    assert "--list-only requires --all." in result.output


def test_cli_rejects_language_without_all() -> None:
    """Verify --language requires --all mode."""
    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--language", "english"])

    assert result.exit_code == VALIDATION_ERROR
    assert "--language requires --all." in result.output


def test_cli_forwards_language_filters_to_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --language is translated into language-code filters for API discovery."""
    observed_languages: set[int] | None = None

    def _collect(
        *_args: object,
        **kwargs: object,
    ) -> list[int]:
        nonlocal observed_languages
        observed_languages = cast("set[int] | None", kwargs["allowed_languages"])
        return [100001]

    _patch_discovery_gateway(monkeypatch, api=_collect)
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--all", "--language", "english", "--language", "spanish"],
    )

    assert result.exit_code == 0
    assert observed_languages == {0, 1}


def test_cli_downloads_with_loader_and_forwards_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --all initializes loader and forwards discovered title IDs."""
    RecordingDownloadRuntime.init_args = None
    RecordingDownloadRuntime.download_args = None
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001, 100002],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--all", "--format", "cbz", "--capture-api", "/tmp/capture", "--out", "/tmp/downloads"],
    )

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.download_args is not None
    assert RecordingDownloadRuntime.init_args["output_format"] == "cbz"
    assert RecordingDownloadRuntime.init_args["capture_api_dir"] == "/tmp/capture"
    assert RecordingDownloadRuntime.download_args["title_ids"] == {100001, 100002}


def test_cli_download_uses_raw_exporter_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --raw switches output format to raw."""
    RecordingDownloadRuntime.init_args = None
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--raw"])

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.init_args["output_format"] == "raw"


def test_cli_fails_when_no_titles_are_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI returns error when scraper finds no title IDs."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=lambda *_args, **_kwargs: [],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--no-browser-fallback"])

    assert result.exit_code != 0
    assert "No title IDs found on configured list pages." in result.output


def test_cli_fails_when_language_filter_has_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify empty API results with language filters raise a targeted message."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=lambda *_args, **_kwargs: [100001],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--language", "german"])

    assert result.exit_code != 0
    assert "No title IDs found for selected language filter(s): german." in result.output


def test_cli_fails_when_scraper_request_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify scraper request exceptions are surfaced as click errors."""

    def _raise_error(*_args: object, **_kwargs: object) -> list[int]:
        raise requests.RequestException("network")

    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=_raise_error,
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--no-browser-fallback"])

    assert result.exit_code != 0
    assert "Failed to fetch title pages: network" in result.output


def test_cli_fails_when_language_filter_api_request_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify language filtering stops when API request fails."""

    def _raise_api_error(*_args: object, **_kwargs: object) -> list[int]:
        raise requests.RequestException("api down")

    _patch_discovery_gateway(monkeypatch, api=_raise_api_error)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--language", "english"])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Language filtering requires API title-index access" in result.output


def test_cli_json_list_only_returns_structured_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --json --all --list-only emits machine-readable title discovery output."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001, 100002],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--all", "--list-only"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "status": "ok",
        "mode": "all_list_only",
        "exit_code": 0,
        "count": 2,
        "title_ids": [100001, 100002],
    }


def test_cli_quiet_list_only_exits_without_human_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --quiet --all --list-only performs discovery and exits quietly."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001, 100002],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--quiet", "--all", "--list-only"])

    assert result.exit_code == 0
    assert result.output == ""


def test_cli_fails_on_subscription_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify subscription failures propagate user-facing click message."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", ShortSubscriptionRequiredDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code != 0
    assert "subscription required" in result.output


def test_cli_all_mode_maps_partial_summary_failures_to_external_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --all returns external-failure exit code for partial chapter failures."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", SinglePartialFailureDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Download completed with 1 failed chapter(s)." in result.output


def test_cli_fails_on_generic_loader_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify generic loader exceptions are wrapped as download failures."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RuntimeFailingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code != 0
    assert "Download failed" in result.output


def test_cli_uses_browser_fallback_when_static_scrape_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify browser fallback is used when static extraction returns no IDs."""
    RecordingDownloadRuntime.download_args = None
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=lambda *_args, **_kwargs: [],
        browser=lambda *_args, **_kwargs: [100010, 100011],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.download_args is not None
    assert RecordingDownloadRuntime.download_args["title_ids"] == {100010, 100011}


def test_cli_can_disable_browser_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify disabling browser fallback keeps empty-result failure behavior."""
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=lambda *_args, **_kwargs: [],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--no-browser-fallback"])

    assert result.exit_code != 0
    assert "No title IDs found on configured list pages." in result.output


def test_cli_fails_when_browser_fallback_raises_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify browser fallback runtime failures are surfaced as click errors."""

    def _raise_runtime(*_args: object, **_kwargs: object) -> list[int]:
        raise RuntimeError("browser missing")

    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=lambda *_args, **_kwargs: [],
        browser=_raise_runtime,
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code != 0
    assert "browser missing" in result.output


def test_cli_fails_when_browser_fallback_raises_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify unexpected browser fallback errors are wrapped predictably."""

    def _raise_generic(*_args: object, **_kwargs: object) -> list[int]:
        raise ValueError("bad page")

    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=lambda *_args, **_kwargs: [],
        browser=_raise_generic,
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code != 0
    assert "Browser fallback failed: bad page" in result.output


def test_cli_uses_browser_fallback_when_static_fetch_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify static fetch errors are reported before browser fallback succeeds."""

    def _raise_static_error(*_args: object, **_kwargs: object) -> list[int]:
        raise requests.RequestException("static down")

    RecordingDownloadRuntime.download_args = None
    _patch_discovery_gateway(
        monkeypatch,
        api=lambda *_args, **_kwargs: [],
        static=_raise_static_error,
        browser=lambda *_args, **_kwargs: [100070],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == 0
    assert "Static fetch failed: static down. Retrying with browser fallback." in result.output
    assert RecordingDownloadRuntime.download_args is not None
    assert RecordingDownloadRuntime.download_args["title_ids"] == {100070}


def test_cli_can_use_static_scrape_when_api_fetch_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify static scrape fallback can recover after API request failure."""

    def _raise_api_error(*_args: object, **_kwargs: object) -> list[int]:
        raise requests.RequestException("api down")

    RecordingDownloadRuntime.download_args = None
    _patch_discovery_gateway(
        monkeypatch,
        api=_raise_api_error,
        static=lambda *_args, **_kwargs: [100050],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == 0
    assert "API title-index fetch failed: api down" in result.output
    assert RecordingDownloadRuntime.download_args is not None
    assert RecordingDownloadRuntime.download_args["title_ids"] == {100050}


def test_cli_can_use_static_scrape_when_api_payload_is_unusable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify static scrape fallback can recover after API payload/schema errors."""

    def _raise_api_error(*_args: object, **_kwargs: object) -> list[int]:
        raise APIResponseError("schema drift", kind="unknown")

    RecordingDownloadRuntime.download_args = None
    _patch_discovery_gateway(
        monkeypatch,
        api=_raise_api_error,
        static=lambda *_args, **_kwargs: [100051],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == 0
    assert "API title-index payload unusable: schema drift" in result.output
    assert RecordingDownloadRuntime.download_args is not None
    assert RecordingDownloadRuntime.download_args["title_ids"] == {100051}
