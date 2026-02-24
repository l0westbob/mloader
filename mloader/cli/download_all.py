"""Bulk downloader command that discovers MangaPlus title IDs automatically."""

from __future__ import annotations

import re
from functools import partial
from typing import Callable, Literal, Sequence

import click
import requests

from mloader import __version__ as about
from mloader.cli.config import setup_logging
from mloader.constants import Language
from mloader.errors import SubscriptionRequiredError
from mloader.exporters.exporter_base import ExporterBase
from mloader.exporters.init import CBZExporter, PDFExporter, RawExporter
from mloader.manga_loader.init import MangaLoader
from mloader.response_pb2 import Response  # type: ignore

DEFAULT_LIST_PAGES: tuple[str, str, str] = (
    "https://mangaplus.shueisha.co.jp/manga_list/ongoing",
    "https://mangaplus.shueisha.co.jp/manga_list/completed",
    "https://mangaplus.shueisha.co.jp/manga_list/one_shot",
)
DEFAULT_TITLE_INDEX_ENDPOINT = "https://jumpg-webapi.tokyo-cdn.com/api/title_list/allV2"
# Match both '/titles/123' and escaped '\/titles\/123' shapes.
TITLE_ID_PATTERN = re.compile(r"(?:\\?/titles\\?/)(?P<title_id>\d+)(?:\\?/|$|[?#\"'])")
LANGUAGE_FILTER_CODES: dict[str, set[int]] = {
    language.name.lower(): {language.value} for language in Language
}
LANGUAGE_FILTER_CODES["vietnamese"].add(8)
LANGUAGE_FILTER_CHOICES = tuple(LANGUAGE_FILTER_CODES)

OutputFormat = Literal["raw", "cbz", "pdf"]
ExporterClass = Callable[..., ExporterBase]


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


@click.command(
    help="Discover available MangaPlus title IDs and download all of them",
)
@click.option(
    "--out",
    "-o",
    "out_dir",
    type=click.Path(exists=False, writable=True),
    metavar="<directory>",
    default="mloader_downloads",
    show_default=True,
    help="Output directory for downloads",
    envvar="MLOADER_EXTRACT_OUT_DIR",
)
@click.option(
    "--page",
    "pages",
    multiple=True,
    default=DEFAULT_LIST_PAGES,
    show_default=True,
    help="MangaPlus list page to scrape for title links (repeatable)",
)
@click.option(
    "--title-index-endpoint",
    type=str,
    default=DEFAULT_TITLE_INDEX_ENDPOINT,
    show_default=True,
    help="MangaPlus web API endpoint used for API-first title discovery",
    envvar="MLOADER_TITLE_INDEX_ENDPOINT",
)
@click.option(
    "--id-length",
    type=click.IntRange(min=1),
    default=None,
    help="If set, keep only title IDs with this exact digit length",
)
@click.option(
    "--language",
    "languages",
    multiple=True,
    type=click.Choice(LANGUAGE_FILTER_CHOICES, case_sensitive=False),
    help="Restrict API discovery to one or more languages (repeatable)",
)
@click.option(
    "--list-only",
    is_flag=True,
    default=False,
    show_default=True,
    help="Only print discovered title IDs and exit",
)
@click.option(
    "--browser-fallback/--no-browser-fallback",
    default=True,
    show_default=True,
    help="Use Playwright-rendered DOM scraping when static page fetch yields no title IDs",
)
@click.option(
    "--raw",
    "-r",
    is_flag=True,
    default=False,
    show_default=True,
    help="Save raw images",
    envvar="MLOADER_RAW",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["cbz", "pdf"], case_sensitive=False),
    default="pdf",
    show_default=True,
    help="Save as CBZ or PDF",
    envvar="MLOADER_OUTPUT_FORMAT",
)
@click.option(
    "--quality",
    "-q",
    default="super_high",
    type=click.Choice(["super_high", "high", "low"]),
    show_default=True,
    help="Image quality",
    envvar="MLOADER_QUALITY",
)
@click.option(
    "--split",
    "-s",
    is_flag=True,
    default=False,
    show_default=True,
    help="Split combined images",
    envvar="MLOADER_SPLIT",
)
@click.option(
    "--begin",
    "-b",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Minimal chapter to download",
)
@click.option(
    "--end",
    "-e",
    type=click.IntRange(min=1),
    help="Maximal chapter to download",
)
@click.option(
    "--last",
    "-l",
    is_flag=True,
    default=False,
    show_default=True,
    help="Download only the last chapter for each title",
)
@click.option(
    "--chapter-title",
    is_flag=True,
    default=False,
    show_default=True,
    help="Include chapter titles in filenames",
)
@click.option(
    "--chapter-subdir",
    is_flag=True,
    default=False,
    show_default=True,
    help="Save raw images in subdirectories by chapter",
)
@click.option(
    "--meta/--no-meta",
    default=True,
    show_default=True,
    help="Export additional metadata as JSON",
)
@click.option(
    "--capture-api",
    "capture_api_dir",
    type=click.Path(file_okay=False, writable=True),
    metavar="<directory>",
    help="Dump raw API payload captures (protobuf + metadata) to this directory",
    envvar="MLOADER_CAPTURE_API_DIR",
)
def main(
    out_dir: str,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    list_only: bool,
    browser_fallback: bool,
    raw: bool,
    output_format: str,
    quality: str,
    split: bool,
    begin: int,
    end: int | None,
    last: bool,
    chapter_title: bool,
    chapter_subdir: bool,
    meta: bool,
    capture_api_dir: str | None,
) -> None:
    """Run bulk-discovery, then download all discovered titles."""
    setup_logging()
    click.echo(click.style(about.__intro__, fg="blue"))

    allowed_languages = parse_language_filters(languages)
    title_ids: list[int] = []
    try:
        title_ids = collect_title_ids_from_api(
            title_index_endpoint,
            id_length=id_length,
            allowed_languages=allowed_languages,
        )
    except requests.RequestException as exc:
        if allowed_languages is not None:
            raise click.ClickException(
                "Language filtering requires API title-index access, but the API request failed: "
                f"{exc}"
            ) from exc
        click.echo(f"API title-index fetch failed: {exc}")

    if not title_ids and allowed_languages is None:
        try:
            title_ids = collect_title_ids(pages, id_length=id_length)
        except requests.RequestException as exc:
            if not browser_fallback:
                raise click.ClickException(f"Failed to fetch title pages: {exc}") from exc
            click.echo(f"Static fetch failed: {exc}. Retrying with browser fallback.")

    if not title_ids and browser_fallback and allowed_languages is None:
        try:
            title_ids = collect_title_ids_with_browser(pages, id_length=id_length)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive browser failures
            raise click.ClickException(f"Browser fallback failed: {exc}") from exc

    if not title_ids and allowed_languages is not None:
        selected_languages = ", ".join(language.lower() for language in languages)
        raise click.ClickException(
            f"No title IDs found for selected language filter(s): {selected_languages}."
        )

    if not title_ids:
        raise click.ClickException(
            "No title IDs found on configured list pages. "
            "Try enabling browser fallback or verify page access."
        )

    click.echo(f"Discovered {len(title_ids)} title ID(s).")
    if list_only:
        click.echo(" ".join(str(title_id) for title_id in title_ids))
        return

    max_chapter = end if end is not None else 2_147_483_647

    exporter_class: ExporterClass
    effective_output_format: OutputFormat
    if raw:
        exporter_class = RawExporter
        effective_output_format = "raw"
    elif output_format == "pdf":
        exporter_class = PDFExporter
        effective_output_format = "pdf"
    else:
        exporter_class = CBZExporter
        effective_output_format = "cbz"

    exporter_factory = partial(
        exporter_class,
        destination=out_dir,
        add_chapter_title=chapter_title,
        add_chapter_subdir=chapter_subdir,
    )
    loader = MangaLoader(
        exporter_factory,
        quality,
        split,
        meta,
        destination=out_dir,
        output_format=effective_output_format,
        capture_api_dir=capture_api_dir,
    )
    try:
        loader.download(
            title_ids=title_ids,
            min_chapter=begin,
            max_chapter=max_chapter,
            last_chapter=last,
        )
    except SubscriptionRequiredError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(f"Download failed: {exc}") from exc
