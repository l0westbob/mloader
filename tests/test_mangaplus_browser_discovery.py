"""Tests for browser-rendered MangaPlus list-page discovery."""

from __future__ import annotations

import sys
import types

import pytest

from mloader.infrastructure.mangaplus import browser_discovery


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
    setattr(sync_api_module, "sync_playwright", lambda: DummyPlaywrightContext())
    playwright_module = types.ModuleType("playwright")
    setattr(playwright_module, "sync_api", sync_api_module)
    monkeypatch.setitem(sys.modules, "playwright", playwright_module)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api_module)

    result = browser_discovery.collect_title_ids_with_browser(
        ["https://a.example", "https://b.example"],
        id_length=6,
    )

    assert result == [100001, 100003]
