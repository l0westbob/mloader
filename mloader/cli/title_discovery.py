"""Title-discovery helpers for ``mloader --all`` mode."""

from __future__ import annotations

import re
from typing import Sequence

import requests

from mloader.constants import Language
from mloader.response_pb2 import Response  # type: ignore

DEFAULT_LIST_PAGES: tuple[str, str, str] = (
    "https://mangaplus.shueisha.co.jp/manga_list/ongoing",
    "https://mangaplus.shueisha.co.jp/manga_list/completed",
    "https://mangaplus.shueisha.co.jp/manga_list/one_shot",
)
DEFAULT_TITLE_INDEX_ENDPOINT = "https://jumpg-webapi.tokyo-cdn.com/api/title_list/allV2"
# Match both '/titles/123' and escaped '\/titles\/123' shapes.
TITLE_ID_PATTERN = re.compile(r"\\?/titles\\?/(?P<title_id>\d+)(?:\\?/|$|[?#\"'])")
LANGUAGE_FILTER_CODES: dict[str, set[int]] = {
    language.name.lower(): {language.value} for language in Language
}
LANGUAGE_FILTER_CODES["vietnamese"].add(8)
LANGUAGE_FILTER_CHOICES = tuple(LANGUAGE_FILTER_CODES)


def extract_title_ids(html: str, id_length: int | None = 6) -> set[int]:
    """Extract unique MangaPlus title IDs from HTML content."""
    title_ids: set[int] = set()
    for match in TITLE_ID_PATTERN.finditer(html):
        title_id = match.group("title_id")
        if id_length is not None and len(title_id) != id_length:
            continue
        title_ids.add(int(title_id))
    return title_ids


def extract_title_ids_from_api_payload(payload: bytes, id_length: int | None = 6) -> set[int]:
    """Extract unique MangaPlus title IDs from protobuf all-titles payload bytes."""
    return extract_title_ids_from_api_payload_with_language_filter(
        payload,
        id_length=id_length,
        allowed_languages=None,
    )


def extract_title_ids_from_api_payload_with_language_filter(
    payload: bytes,
    *,
    id_length: int | None,
    allowed_languages: set[int] | None,
) -> set[int]:
    """Extract unique title IDs with an optional language-code filter."""
    parsed = Response.FromString(payload)
    title_ids: set[int] = set()
    for title_group in parsed.success.all_titles_view.title_groups:
        for title in title_group.titles:
            title_id = title.title_id
            if allowed_languages is not None and title.language not in allowed_languages:
                continue
            if title_id <= 0:
                continue
            if id_length is not None and len(str(title_id)) != id_length:
                continue
            title_ids.add(int(title_id))
    return title_ids


def collect_title_ids_from_api(
    title_index_endpoint: str,
    *,
    id_length: int | None,
    allowed_languages: set[int] | None,
    request_timeout: tuple[float, float] = (5.0, 30.0),
) -> list[int]:
    """Fetch web title-index payload and return sorted unique title IDs."""
    with requests.Session() as session:
        response = session.get(title_index_endpoint, timeout=request_timeout)
        response.raise_for_status()
        title_ids = extract_title_ids_from_api_payload_with_language_filter(
            response.content,
            id_length=id_length,
            allowed_languages=allowed_languages,
        )
    return sorted(title_ids)


def parse_language_filters(languages: Sequence[str]) -> set[int] | None:
    """Convert language filter strings into a set of numeric API language codes."""
    if not languages:
        return None

    language_codes: set[int] = set()
    for language in languages:
        language_codes.update(LANGUAGE_FILTER_CODES[language.lower()])
    return language_codes


def collect_title_ids(
    pages: Sequence[str],
    *,
    id_length: int | None,
    request_timeout: tuple[float, float] = (5.0, 30.0),
) -> list[int]:
    """Fetch configured list pages and return sorted unique title IDs."""
    title_ids: set[int] = set()
    with requests.Session() as session:
        for page_url in pages:
            response = session.get(page_url, timeout=request_timeout)
            response.raise_for_status()
            title_ids.update(extract_title_ids(response.text, id_length=id_length))
    return sorted(title_ids)


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
            "Playwright is not installed. Install with 'pip install .[bulk]' and run "
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
