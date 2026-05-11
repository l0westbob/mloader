"""Tests for raw MangaPlus API response classification."""

from __future__ import annotations

from mloader.manga_loader.api_response import (
    classify_api_response_payload,
    format_api_payload_problem,
)
from mloader.response_pb2 import Response


def _varint(value: int) -> bytes:
    """Encode a protobuf varint for fixture construction."""
    parts: list[int] = []
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            parts.append(byte | 0x80)
            continue
        parts.append(byte)
        return bytes(parts)


def _length_delimited_field(field_number: int, value: bytes) -> bytes:
    """Encode one length-delimited protobuf field."""
    key = (field_number << 3) | 2
    return _varint(key) + _varint(len(value)) + value


def _varint_field(field_number: int, value: int) -> bytes:
    """Encode one varint protobuf field."""
    key = field_number << 3
    return _varint(key) + _varint(value)


def _string_field(field_number: int, value: str) -> bytes:
    """Encode one protobuf string field."""
    return _length_delimited_field(field_number, value.encode("utf-8"))


def _api_error_payload(*, message: str, code_language: int = 0) -> bytes:
    """Build a minimal MangaPlus application-error envelope."""
    localized_error = (
        _string_field(1, "Invalid Parameter")
        + _string_field(2, message)
        + _varint_field(6, code_language)
    )
    error_result = _length_delimited_field(2, localized_error)
    return _length_delimited_field(2, error_result)


def test_classify_success_payload() -> None:
    """Verify normal success envelopes classify as success."""
    response = Response()
    group = response.success.all_titles_view.title_groups.add()
    title = group.titles.add()
    title.title_id = 100001
    title.name = "Demo"

    classification = classify_api_response_payload(response.SerializeToString())

    assert classification.kind == "success"
    assert classification.error is None


def test_classify_application_error_envelope() -> None:
    """Verify MangaPlus application-error envelopes expose code and message."""
    payload = _api_error_payload(
        message="There are issues connecting to Manga+. Please try again later.(10511)"
    )

    classification = classify_api_response_payload(payload)

    assert classification.kind == "api_error"
    assert classification.error is not None
    assert classification.error.title == "Invalid Parameter"
    assert classification.error.code == "10511"
    assert "Manga+" in classification.error.body


def test_format_api_payload_problem_mentions_schema_drift_for_unknown() -> None:
    """Verify unknown payloads produce a schema-drift diagnostic."""
    classification = classify_api_response_payload(b"not-protobuf")

    assert classification.kind == "unknown"
    assert "schema drift" in format_api_payload_problem(classification, context="title_index")


def test_empty_payload_classification() -> None:
    """Verify empty response bodies classify explicitly."""
    classification = classify_api_response_payload(b"")

    assert classification.kind == "empty"
    assert "empty payload" in format_api_payload_problem(classification, context="manga_viewer")
