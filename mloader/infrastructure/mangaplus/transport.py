"""Shared MangaPlus HTTP transport and capture helpers."""

from __future__ import annotations

from collections.abc import Mapping

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mloader.infrastructure.mangaplus.settings import (
    MOBILE_API_HEADERS,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUS_CODES,
)
from mloader.types import PayloadCaptureLike, SessionLike


def configure_transport(session: SessionLike, retries: int) -> None:
    """Configure HTTPS retry policy for transient API failures."""
    retry_policy = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_policy)
    session.mount("https://", adapter)


def apply_mobile_api_headers(session: SessionLike) -> None:
    """Apply MangaPlus mobile API headers to an HTTP session."""
    session.headers.update(MOBILE_API_HEADERS)


def capture_response_payload(
    payload_capture: PayloadCaptureLike | None,
    *,
    endpoint: str,
    identifier: str | int,
    url: str,
    params: Mapping[str, object],
    response_content: bytes,
) -> None:
    """Persist an API payload capture record when capture mode is enabled."""
    if payload_capture is None:
        return
    payload_capture.capture(
        endpoint=endpoint,
        identifier=identifier,
        url=url,
        params=params,
        response_content=response_content,
    )
