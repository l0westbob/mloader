"""Static MangaPlus list-page title discovery."""

from __future__ import annotations

import re
from collections.abc import Sequence

import requests

from mloader.infrastructure.mangaplus import settings

# Match both '/titles/123' and escaped '\/titles\/123' shapes.
TITLE_ID_PATTERN = re.compile(r"\\?/titles\\?/(?P<title_id>\d+)(?:\\?/|$|[?#\"'])")


def extract_title_ids(html: str, id_length: int | None = 6) -> set[int]:
    """Extract unique MangaPlus title IDs from HTML content."""
    title_ids: set[int] = set()
    for match in TITLE_ID_PATTERN.finditer(html):
        title_id = match.group("title_id")
        if id_length is not None and len(title_id) != id_length:
            continue
        title_ids.add(int(title_id))
    return title_ids


def collect_title_ids(
    pages: Sequence[str],
    *,
    id_length: int | None,
    request_timeout: tuple[float, float] = settings.DEFAULT_REQUEST_TIMEOUT,
) -> list[int]:
    """Fetch configured list pages and return sorted unique title IDs."""
    title_ids: set[int] = set()
    with requests.Session() as session:
        for page_url in pages:
            response = session.get(page_url, timeout=request_timeout)
            response.raise_for_status()
            title_ids.update(extract_title_ids(response.text, id_length=id_length))
    return sorted(title_ids)
