"""MangaPlus title-index API discovery."""

from __future__ import annotations

import time
from collections.abc import Sequence

import requests

from mloader.constants import Language
from mloader.errors import APIResponseError
from mloader.infrastructure.mangaplus import auth, settings
from mloader.infrastructure.mangaplus.api_response import (
    classify_api_response_payload,
    format_api_payload_problem,
)
from mloader.infrastructure.mangaplus.capture import APIPayloadCapture
from mloader.infrastructure.mangaplus.transport import (
    apply_mobile_api_headers,
    capture_response_payload,
)
from mloader.response_pb2 import Response

DEFAULT_TITLE_INDEX_ENDPOINT = settings.DEFAULT_TITLE_INDEX_ENDPOINT
LANGUAGE_FILTER_CODES: dict[str, set[int]] = {
    language.name.lower(): {language.value} for language in Language
}
LANGUAGE_FILTER_CODES["vietnamese"].add(8)
LANGUAGE_FILTER_CHOICES = tuple(LANGUAGE_FILTER_CODES)
API_RETRY_STATUS_CODES: set[int] = set(settings.RETRY_STATUS_CODES)
API_MAX_ATTEMPTS = settings.TITLE_INDEX_MAX_ATTEMPTS
API_RETRY_BACKOFF_SECONDS = settings.TITLE_INDEX_RETRY_BACKOFF_SECONDS


def parse_language_filters(languages: Sequence[str]) -> set[int] | None:
    """Convert language filter strings into a set of numeric API language codes."""
    if not languages:
        return None

    language_codes: set[int] = set()
    for language in languages:
        language_codes.update(LANGUAGE_FILTER_CODES[language.lower()])
    return language_codes


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
    classification = classify_api_response_payload(payload)
    if classification.kind != "success":
        raise APIResponseError(
            format_api_payload_problem(classification, context="title_index"),
            kind=classification.kind if classification.kind != "success" else "unknown",
            code=classification.error.code if classification.error else None,
        )

    parsed = Response.FromString(payload)
    if not parsed.success.HasField("all_titles_view"):
        raise APIResponseError(
            "MangaPlus title-index API returned a success payload without all_titles_view; "
            "this may indicate API schema drift.",
            kind="unknown",
        )

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
    request_timeout: tuple[float, float] = settings.DEFAULT_REQUEST_TIMEOUT,
    capture_api_dir: str | None = None,
) -> list[int]:
    """Fetch mobile title-index payload and return sorted unique title IDs."""
    with requests.Session() as session:
        apply_mobile_api_headers(session)
        last_error: requests.RequestException | None = None
        payload_capture = APIPayloadCapture(capture_api_dir) if capture_api_dir else None
        for attempt in range(1, API_MAX_ATTEMPTS + 1):
            try:
                auth_params = auth.auth_params()
                response = session.get(
                    title_index_endpoint,
                    params=auth_params,
                    timeout=request_timeout,
                )
                response.raise_for_status()
                capture_response_payload(
                    payload_capture,
                    endpoint="title_index",
                    identifier="all",
                    url=title_index_endpoint,
                    params={
                        **auth_params,
                        "allowed_languages": sorted(allowed_languages)
                        if allowed_languages is not None
                        else "all",
                        "id_length": id_length if id_length is not None else "any",
                    },
                    response_content=response.content,
                )
                title_ids = extract_title_ids_from_api_payload_with_language_filter(
                    response.content,
                    id_length=id_length,
                    allowed_languages=allowed_languages,
                )
                return sorted(title_ids)
            except requests.HTTPError as error:
                status_code = error.response.status_code if error.response is not None else None
                if status_code in API_RETRY_STATUS_CODES and attempt < API_MAX_ATTEMPTS:
                    time.sleep(API_RETRY_BACKOFF_SECONDS * attempt)
                    last_error = error
                    continue
                raise
            except requests.RequestException as error:
                if attempt < API_MAX_ATTEMPTS:
                    time.sleep(API_RETRY_BACKOFF_SECONDS * attempt)
                    last_error = error
                    continue
                raise

    if last_error is not None:  # pragma: no cover - final retry raises in-loop
        raise last_error
    return []  # pragma: no cover - API_MAX_ATTEMPTS is always positive
