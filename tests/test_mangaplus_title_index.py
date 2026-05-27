"""Tests for MangaPlus title-index API discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from mloader.errors import APIResponseError
from mloader.infrastructure.mangaplus import auth, title_index
from mloader.response_pb2 import Response
from tests.http_fakes import BytesMappingSession, BytesResponse


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


def test_extract_title_ids_from_api_payload_respects_id_length_filter() -> None:
    """Verify binary API extraction keeps IDs matching configured digit length."""
    payload = _build_all_titles_payload([100001, 99999])
    assert title_index.extract_title_ids_from_api_payload(payload, id_length=6) == {100001}
    assert title_index.extract_title_ids_from_api_payload(payload, id_length=None) == {
        99999,
        100001,
    }


def test_extract_title_ids_from_api_payload_skips_non_positive_ids() -> None:
    """Verify protobuf extraction ignores non-positive title IDs."""
    parsed = Response()
    group = parsed.success.all_titles_view.title_groups.add()
    title = group.titles.add()
    title.title_id = 0

    assert (
        title_index.extract_title_ids_from_api_payload(
            parsed.SerializeToString(),
            id_length=None,
        )
        == set()
    )


def test_extract_title_ids_from_api_payload_filters_languages() -> None:
    """Verify protobuf extraction can filter by allowed language codes."""
    payload = _build_all_titles_payload_with_languages(
        [
            (100001, 0),
            (100002, 1),
            (100003, 0),
        ]
    )

    result = title_index.extract_title_ids_from_api_payload_with_language_filter(
        payload,
        id_length=6,
        allowed_languages={0},
    )

    assert result == {100001, 100003}


def test_extract_title_ids_from_api_payload_rejects_unknown_payload() -> None:
    """Verify title-index parsing reports schema drift for undecodable payloads."""
    with pytest.raises(APIResponseError, match="schema drift") as error:
        title_index.extract_title_ids_from_api_payload(b"not-protobuf")

    assert error.value.kind == "unknown"


def test_extract_title_ids_from_api_payload_rejects_success_without_title_index() -> None:
    """Verify success envelopes without all_titles_view are reported as schema drift."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100001
    parsed.success.title_detail_view.title.name = "Other payload"

    with pytest.raises(APIResponseError, match="without all_titles_view") as error:
        title_index.extract_title_ids_from_api_payload(
            parsed.SerializeToString(),
            id_length=None,
        )

    assert error.value.kind == "unknown"


def test_collect_title_ids_from_api_returns_sorted_unique_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify API scraper deduplicates IDs and returns sorted list."""
    payload = _build_all_titles_payload([100003, 100001, 100001, 100002])
    dummy_session = BytesMappingSession({"https://api.example/allV2": payload})
    monkeypatch.setattr(title_index.requests, "Session", lambda: dummy_session)

    result = title_index.collect_title_ids_from_api(
        "https://api.example/allV2",
        id_length=6,
        allowed_languages=None,
    )

    assert result == [100001, 100002, 100003]
    assert dummy_session.calls == [("https://api.example/allV2", auth.auth_params(), (5.0, 30.0))]
    assert dummy_session.headers["User-Agent"] == "okhttp/4.12.0"
    assert "Host" not in dummy_session.headers


def test_collect_title_ids_from_api_captures_title_index_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify capture mode stores title-index payloads during --all discovery."""
    payload = _build_all_titles_payload([100001])
    dummy_session = BytesMappingSession({"https://api.example/allV2": payload})
    monkeypatch.setattr(title_index.requests, "Session", lambda: dummy_session)

    result = title_index.collect_title_ids_from_api(
        "https://api.example/allV2",
        id_length=6,
        allowed_languages={0},
        capture_api_dir=str(tmp_path),
    )

    assert result == [100001]
    metadata = json.loads(next(tmp_path.glob("*.meta.json")).read_text(encoding="utf-8"))
    assert metadata["endpoint"] == "title_index"
    assert metadata["payload_classification"] == "success"
    assert metadata["params"]["allowed_languages"] == [0]


def test_collect_title_ids_from_api_retries_transient_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify API scraper retries temporary upstream errors before succeeding."""
    payload = _build_all_titles_payload([100002, 100001])

    class FlakySession:
        """Session test double failing once with HTTP 502 then succeeding."""

        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str] | None, tuple[float, float]]] = []
            self._attempt = 0
            self.headers: dict[str, str] = {}

        def __enter__(self) -> FlakySession:
            return self

        def __exit__(self, *args: object) -> None:
            _ = args

        def get(
            self,
            url: str,
            params: dict[str, str] | None = None,
            timeout: tuple[float, float] = (5.0, 30.0),
        ) -> BytesResponse:
            self.calls.append((url, params, timeout))
            self._attempt += 1
            if self._attempt == 1:
                return BytesResponse(status_code=502)
            return BytesResponse(content=payload)

    flaky_session = FlakySession()
    monkeypatch.setattr(title_index.requests, "Session", lambda: flaky_session)
    monkeypatch.setattr(title_index.time, "sleep", lambda _seconds: None)

    result = title_index.collect_title_ids_from_api(
        "https://api.example/allV2",
        id_length=6,
        allowed_languages=None,
    )

    assert result == [100001, 100002]
    assert len(flaky_session.calls) == 2


def test_collect_title_ids_from_api_does_not_retry_non_transient_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify non-transient HTTP errors surface immediately."""
    dummy_session = BytesMappingSession(
        {"https://api.example/allV2": BytesResponse(status_code=404)}
    )
    monkeypatch.setattr(title_index.requests, "Session", lambda: dummy_session)

    with pytest.raises(requests.HTTPError, match="404 error"):
        title_index.collect_title_ids_from_api(
            "https://api.example/allV2",
            id_length=6,
            allowed_languages=None,
        )


def test_collect_title_ids_from_api_retries_request_errors_until_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify repeated network errors are retried and then surfaced."""

    class FailingSession:
        """Session test double raising request errors on every attempt."""

        def __init__(self) -> None:
            self.calls = 0
            self.headers: dict[str, str] = {}

        def __enter__(self) -> FailingSession:
            return self

        def __exit__(self, *args: object) -> None:
            _ = args

        def get(
            self,
            _url: str,
            params: dict[str, str] | None = None,
            timeout: tuple[float, float] = (5.0, 30.0),
        ) -> BytesResponse:
            del params
            del timeout
            self.calls += 1
            raise requests.RequestException("network down")

    failing_session = FailingSession()
    monkeypatch.setattr(title_index.requests, "Session", lambda: failing_session)
    monkeypatch.setattr(title_index.time, "sleep", lambda _seconds: None)

    with pytest.raises(requests.RequestException, match="network down"):
        title_index.collect_title_ids_from_api(
            "https://api.example/allV2",
            id_length=6,
            allowed_languages=None,
        )

    assert failing_session.calls == title_index.API_MAX_ATTEMPTS


def test_parse_language_filters_returns_none_for_empty_input() -> None:
    """Verify empty language filters preserve unfiltered behavior."""
    assert title_index.parse_language_filters(()) is None


def test_parse_language_filters_merges_multiple_languages() -> None:
    """Verify language filter parser resolves multiple language selectors."""
    result = title_index.parse_language_filters(("english", "vietnamese"))

    assert result is not None
    assert 0 in result
    assert 9 in result
    assert 8 in result
