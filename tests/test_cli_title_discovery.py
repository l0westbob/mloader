"""Tests for title discovery utilities and ``mloader --all`` orchestration."""

from __future__ import annotations

import json
import types
import sys
from typing import Any, ClassVar

import pytest
import requests
from click.testing import CliRunner

from mloader.cli.exit_codes import EXTERNAL_FAILURE, VALIDATION_ERROR
from mloader.cli import title_discovery
from mloader.cli import main as cli_main
from mloader.domain.requests import DownloadSummary
from mloader.errors import SubscriptionRequiredError
from mloader.response_pb2 import Response  # type: ignore


class DummyResponse:
    """Minimal response test double for scraper requests."""

    def __init__(self, text: str = "", content: bytes | None = None) -> None:
        """Store response body for extraction tests."""
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")

    def raise_for_status(self) -> None:
        """Simulate successful response status."""


class DummySession:
    """Session test double yielding deterministic page content."""

    def __init__(self, payloads: dict[str, str | bytes]) -> None:
        """Store URL-to-payload mapping for request simulations."""
        self.payloads = payloads
        self.calls: list[tuple[str, tuple[float, float]]] = []

    def __enter__(self) -> DummySession:
        """Support context manager protocol."""
        return self

    def __exit__(self, *args: object) -> None:
        """Support context manager protocol."""
        _ = args

    def get(self, url: str, timeout: tuple[float, float]) -> DummyResponse:
        """Record request and return mapped HTML payload."""
        self.calls.append((url, timeout))
        payload = self.payloads[url]
        if isinstance(payload, bytes):
            return DummyResponse(content=payload)
        return DummyResponse(text=payload)


class DummyLoader:
    """Loader test double capturing init and download payloads."""

    init_args: ClassVar[dict[str, Any] | None] = None
    download_args: ClassVar[dict[str, Any] | None] = None

    def __init__(
        self,
        exporter_factory: Any,
        quality: str,
        split: bool,
        meta: bool,
        destination: str,
        output_format: str,
        capture_api_dir: str | None,
        resume: bool,
        manifest_reset: bool,
    ) -> None:
        """Store initializer payload for assertions."""
        type(self).init_args = {
            "exporter_factory": exporter_factory,
            "quality": quality,
            "split": split,
            "meta": meta,
            "destination": destination,
            "output_format": output_format,
            "capture_api_dir": capture_api_dir,
            "resume": resume,
            "manifest_reset": manifest_reset,
        }

    def download(self, **kwargs: Any) -> DownloadSummary:
        """Store download payload for assertions."""
        type(self).download_args = kwargs
        return DownloadSummary(
            downloaded=1,
            skipped_manifest=0,
            failed=0,
            failed_chapter_ids=(),
        )


class FailingLoader(DummyLoader):
    """Loader test double raising generic runtime exceptions."""

    def download(self, **kwargs: Any) -> None:
        """Raise generic runtime failure for CLI error handling path."""
        del kwargs
        raise RuntimeError("boom")


class SubscriptionLoader(DummyLoader):
    """Loader test double raising subscription errors."""

    def download(self, **kwargs: Any) -> None:
        """Raise subscription error for CLI message handling path."""
        del kwargs
        raise SubscriptionRequiredError("subscription required")


class PartialFailureLoader(DummyLoader):
    """Loader test double returning summary with failed chapters."""

    def download(self, **kwargs: Any) -> DownloadSummary:
        """Return a deterministic partial-failure summary."""
        del kwargs
        return DownloadSummary(
            downloaded=1,
            skipped_manifest=0,
            failed=1,
            failed_chapter_ids=(123,),
        )


def _build_all_titles_payload(title_ids: list[int]) -> bytes:
    """Build a minimal serialized all-titles protobuf payload for tests."""
    parsed = Response()
    group = parsed.success.all_titles_view.title_groups.add()
    group.group_name = "group"
    for title_id in title_ids:
        title = group.titles.add()
        title.title_id = title_id
        title.name = f"title-{title_id}"
    return parsed.SerializeToString()


def _build_all_titles_payload_with_languages(titles: list[tuple[int, int]]) -> bytes:
    """Build a minimal serialized all-titles protobuf payload with language codes."""
    parsed = Response()
    group = parsed.success.all_titles_view.title_groups.add()
    group.group_name = "group"
    for title_id, language in titles:
        title = group.titles.add()
        title.title_id = title_id
        title.name = f"title-{title_id}"
        title.language = language
    return parsed.SerializeToString()


def test_extract_title_ids_respects_id_length_filter() -> None:
    """Verify HTML extraction keeps only IDs matching configured digit length."""
    html = (
        '<a href="/titles/123456">ok</a>'
        '<a href="/titles/10031">short</a>'
        '<a href="/titles/123456/">dup</a>'
    )
    assert title_discovery.extract_title_ids(html, id_length=6) == {123456}
    assert title_discovery.extract_title_ids(html, id_length=None) == {10031, 123456}


def test_extract_title_ids_matches_escaped_slash_links() -> None:
    """Verify extractor supports escaped JSON-style title links."""
    html = r'{"href":"\/titles\/123456\/"}{"href":"\/titles\/654321"}'
    assert title_discovery.extract_title_ids(html, id_length=None) == {123456, 654321}


def test_extract_title_ids_from_api_payload_respects_id_length_filter() -> None:
    """Verify binary API extraction keeps IDs matching configured digit length."""
    payload = _build_all_titles_payload([100001, 99999])
    assert title_discovery.extract_title_ids_from_api_payload(payload, id_length=6) == {100001}
    assert title_discovery.extract_title_ids_from_api_payload(payload, id_length=None) == {
        99999,
        100001,
    }


def test_extract_title_ids_from_api_payload_skips_non_positive_ids() -> None:
    """Verify protobuf extraction ignores non-positive title IDs."""
    parsed = Response()
    group = parsed.success.all_titles_view.title_groups.add()
    title = group.titles.add()
    title.title_id = 0

    assert title_discovery.extract_title_ids_from_api_payload(
        parsed.SerializeToString(),
        id_length=None,
    ) == set()


def test_extract_title_ids_from_api_payload_filters_languages() -> None:
    """Verify protobuf extraction can filter by allowed language codes."""
    payload = _build_all_titles_payload_with_languages(
        [
            (100001, 0),
            (100002, 1),
            (100003, 0),
        ]
    )

    result = title_discovery.extract_title_ids_from_api_payload_with_language_filter(
        payload,
        id_length=6,
        allowed_languages={0},
    )

    assert result == {100001, 100003}


def test_collect_title_ids_from_api_returns_sorted_unique_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify API scraper deduplicates IDs and returns sorted list."""
    payload = _build_all_titles_payload([100003, 100001, 100001, 100002])
    dummy_session = DummySession({"https://api.example/allV2": payload})
    monkeypatch.setattr(title_discovery.requests, "Session", lambda: dummy_session)

    result = title_discovery.collect_title_ids_from_api(
        "https://api.example/allV2",
        id_length=6,
        allowed_languages=None,
    )

    assert result == [100001, 100002, 100003]
    assert dummy_session.calls == [("https://api.example/allV2", (5.0, 30.0))]


def test_collect_title_ids_returns_sorted_unique_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify scraper deduplicates IDs and returns sorted list."""
    payloads = {
        "https://a.example": '<a href="/titles/100003">A</a><a href="/titles/100001">B</a>',
        "https://b.example": '<a href="/titles/100001">C</a><a href="/titles/100002">D</a>',
    }
    dummy_session = DummySession(payloads)
    monkeypatch.setattr(title_discovery.requests, "Session", lambda: dummy_session)

    result = title_discovery.collect_title_ids(
        ["https://a.example", "https://b.example"],
        id_length=6,
    )

    assert result == [100001, 100002, 100003]
    assert dummy_session.calls == [
        ("https://a.example", (5.0, 30.0)),
        ("https://b.example", (5.0, 30.0)),
    ]


def test_parse_language_filters_returns_none_for_empty_input() -> None:
    """Verify empty language filters preserve unfiltered behavior."""
    assert title_discovery.parse_language_filters(()) is None


def test_parse_language_filters_merges_multiple_languages() -> None:
    """Verify language filter parser resolves multiple language selectors."""
    result = title_discovery.parse_language_filters(("english", "vietnamese"))

    assert result is not None
    assert 0 in result
    assert 9 in result
    assert 8 in result


def test_collect_title_ids_with_browser_returns_sorted_unique_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify browser scrape can collect IDs via rendered DOM links."""

    class DummyLink:
        """Link test double with optional href attribute."""

        def __init__(self, href: str | None) -> None:
            """Store href value returned by DOM attribute access."""
            self.href = href

        def get_attribute(self, _name: str) -> str | None:
            """Return configured href value."""
            return self.href

    class DummyPage:
        """Page test double with deterministic links for all requested pages."""

        def goto(self, *_args: object, **_kwargs: object) -> None:
            """Accept navigation calls without side effects."""

        def query_selector_all(self, _selector: str) -> list[DummyLink]:
            """Return deterministic set of DOM links for extraction."""
            return [
                DummyLink("/titles/100003"),
                DummyLink("/titles/100001/"),
                DummyLink("/titles/100001"),
                DummyLink(None),
            ]

    class DummyBrowser:
        """Browser test double producing a single page object."""

        def new_page(self) -> DummyPage:
            """Return page test double for scrape actions."""
            return DummyPage()

        def close(self) -> None:
            """Support browser lifecycle teardown call."""

    class DummyChromium:
        """Chromium launcher test double."""

        def launch(self, *, headless: bool) -> DummyBrowser:
            """Return browser test double for headless mode."""
            assert headless is True
            return DummyBrowser()

    class DummyPlaywright:
        """Playwright root object exposing chromium launcher."""

        chromium = DummyChromium()

    class DummyPlaywrightContext:
        """Context-manager test double returned by sync_playwright()."""

        def __enter__(self) -> DummyPlaywright:
            """Return playwright object for context manager body."""
            return DummyPlaywright()

        def __exit__(self, *args: object) -> None:
            """Support context manager protocol."""
            _ = args

    sync_api_module = types.ModuleType("playwright.sync_api")
    sync_api_module.sync_playwright = lambda: DummyPlaywrightContext()
    playwright_module = types.ModuleType("playwright")
    playwright_module.sync_api = sync_api_module
    monkeypatch.setitem(sys.modules, "playwright", playwright_module)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api_module)

    result = title_discovery.collect_title_ids_with_browser(
        ["https://a.example", "https://b.example"],
        id_length=6,
    )

    assert result == [100001, 100003]


def test_cli_list_only_prints_ids_without_downloading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --all --list-only prints IDs and exits before loader initialization."""
    DummyLoader.init_args = None
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001, 100002],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--list-only"])

    assert result.exit_code == 0
    assert "100001 100002" in result.output
    assert DummyLoader.init_args is None


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
        observed_languages = kwargs["allowed_languages"]  # type: ignore[index]
        return [100001]

    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids_from_api", _collect)
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

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
    DummyLoader.init_args = None
    DummyLoader.download_args = None
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001, 100002],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--all", "--format", "cbz", "--capture-api", "/tmp/capture", "--out", "/tmp/downloads"],
    )

    assert result.exit_code == 0
    assert DummyLoader.init_args is not None
    assert DummyLoader.download_args is not None
    assert DummyLoader.init_args["output_format"] == "cbz"
    assert DummyLoader.init_args["capture_api_dir"] == "/tmp/capture"
    assert DummyLoader.download_args["title_ids"] == {100001, 100002}


def test_cli_download_uses_raw_exporter_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --raw switches output format to raw."""
    DummyLoader.init_args = None
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--raw"])

    assert result.exit_code == 0
    assert DummyLoader.init_args is not None
    assert DummyLoader.init_args["output_format"] == "raw"


def test_cli_fails_when_no_titles_are_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI returns error when scraper finds no title IDs."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids", lambda *_args, **_kwargs: [])

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--no-browser-fallback"])

    assert result.exit_code != 0
    assert "No title IDs found on configured list pages." in result.output


def test_cli_fails_when_language_filter_has_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify empty API results with language filters raise a targeted message."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids",
        lambda *_args, **_kwargs: [100001],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--language", "german"])

    assert result.exit_code != 0
    assert "No title IDs found for selected language filter(s): german." in result.output


def test_cli_fails_when_scraper_request_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify scraper request exceptions are surfaced as click errors."""

    def _raise_error(*_args: object, **_kwargs: object) -> list[int]:
        raise requests.RequestException("network")

    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids", _raise_error)

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

    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids_from_api", _raise_api_error)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--language", "english"])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Language filtering requires API title-index access" in result.output


def test_cli_json_list_only_returns_structured_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --json --all --list-only emits machine-readable title discovery output."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001, 100002],
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
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001, 100002],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--quiet", "--all", "--list-only"])

    assert result.exit_code == 0
    assert result.output == ""


def test_cli_fails_on_subscription_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify subscription failures propagate user-facing click message."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", SubscriptionLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code != 0
    assert "subscription required" in result.output


def test_cli_all_mode_maps_partial_summary_failures_to_external_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --all returns external-failure exit code for partial chapter failures."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", PartialFailureLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Download completed with 1 failed chapter(s)." in result.output


def test_cli_fails_on_generic_loader_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify generic loader exceptions are wrapped as download failures."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [100001],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", FailingLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code != 0
    assert "Download failed" in result.output


def test_cli_uses_browser_fallback_when_static_scrape_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify browser fallback is used when static extraction returns no IDs."""
    DummyLoader.download_args = None
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_with_browser",
        lambda *_args, **_kwargs: [100010, 100011],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == 0
    assert DummyLoader.download_args is not None
    assert DummyLoader.download_args["title_ids"] == {100010, 100011}


def test_cli_can_disable_browser_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify disabling browser fallback keeps empty-result failure behavior."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids", lambda *_args, **_kwargs: [])

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all", "--no-browser-fallback"])

    assert result.exit_code != 0
    assert "No title IDs found on configured list pages." in result.output


def test_cli_fails_when_browser_fallback_raises_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify browser fallback runtime failures are surfaced as click errors."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids", lambda *_args, **_kwargs: [])

    def _raise_runtime(*_args: object, **_kwargs: object) -> list[int]:
        raise RuntimeError("browser missing")

    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids_with_browser", _raise_runtime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code != 0
    assert "browser missing" in result.output


def test_cli_fails_when_browser_fallback_raises_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify unexpected browser fallback errors are wrapped predictably."""
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids", lambda *_args, **_kwargs: [])

    def _raise_generic(*_args: object, **_kwargs: object) -> list[int]:
        raise ValueError("bad page")

    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids_with_browser", _raise_generic)

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

    DummyLoader.download_args = None
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_from_api",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids", _raise_static_error)
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids_with_browser",
        lambda *_args, **_kwargs: [100070],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == 0
    assert "Static fetch failed: static down. Retrying with browser fallback." in result.output
    assert DummyLoader.download_args is not None
    assert DummyLoader.download_args["title_ids"] == {100070}


def test_cli_can_use_static_scrape_when_api_fetch_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify static scrape fallback can recover after API request failure."""

    def _raise_api_error(*_args: object, **_kwargs: object) -> list[int]:
        raise requests.RequestException("api down")

    DummyLoader.download_args = None
    monkeypatch.setattr(cli_main.title_discovery, "collect_title_ids_from_api", _raise_api_error)
    monkeypatch.setattr(
        cli_main.title_discovery,
        "collect_title_ids",
        lambda *_args, **_kwargs: [100050],
    )
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--all"])

    assert result.exit_code == 0
    assert "API title-index fetch failed: api down" in result.output
    assert DummyLoader.download_args is not None
    assert DummyLoader.download_args["title_ids"] == {100050}
