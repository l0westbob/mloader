"""Browser-rendered MangaPlus list-page title discovery."""

from __future__ import annotations

from collections.abc import Sequence

from mloader.infrastructure.mangaplus.static_discovery import extract_title_ids


def collect_title_ids_with_browser(
    pages: Sequence[str],
    *,
    id_length: int | None,
    timeout_ms: int = 60000,
) -> list[int]:
    """Render list pages in a browser and extract title IDs from DOM links."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - import path is covered by CLI tests
        raise RuntimeError(
            "Playwright is not installed. Install project dependencies with 'uv sync' and run "
            "'playwright install chromium'."
        ) from exc

    title_ids: set[int] = set()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        for page_url in pages:
            page.goto(page_url, wait_until="networkidle", timeout=timeout_ms)
            for link in page.query_selector_all("a[href]"):
                href = link.get_attribute("href")
                if href:
                    title_ids.update(extract_title_ids(href, id_length=id_length))
        browser.close()
    return sorted(title_ids)
