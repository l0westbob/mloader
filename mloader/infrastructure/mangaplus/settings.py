"""Central MangaPlus API endpoint, header, timeout, and retry settings."""

from __future__ import annotations

DEFAULT_API_BASE_URL = "https://jumpg-api.tokyo-cdn.com"
MANGA_VIEWER_PATH = "/api/manga_viewer"
TITLE_DETAIL_PATH = "/api/title_detailV3"
TITLE_INDEX_PATH = "/api/title_list/allV2"

DEFAULT_LIST_PAGES: tuple[str, str, str] = (
    "https://mangaplus.shueisha.co.jp/manga_list/ongoing",
    "https://mangaplus.shueisha.co.jp/manga_list/completed",
    "https://mangaplus.shueisha.co.jp/manga_list/one_shot",
)
DEFAULT_TITLE_INDEX_ENDPOINT = f"{DEFAULT_API_BASE_URL}{TITLE_INDEX_PATH}"
DEFAULT_REQUEST_TIMEOUT = (5.0, 30.0)

MOBILE_API_HEADERS: dict[str, str] = {
    "User-Agent": "okhttp/4.12.0",
    "Accept-Encoding": "gzip",
}

RETRY_STATUS_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)
DEFAULT_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5
TITLE_INDEX_MAX_ATTEMPTS = 3
TITLE_INDEX_RETRY_BACKOFF_SECONDS = 2.0


def api_url(base_url: str, path: str) -> str:
    """Build a MangaPlus API URL from a base URL and path."""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
