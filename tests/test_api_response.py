"""Tests for raw MangaPlus API response classification."""

from __future__ import annotations

import pytest

from mloader.manga_loader import api_response
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


def _fixed64_field(field_number: int) -> bytes:
    """Encode one fixed64 protobuf field."""
    return _varint((field_number << 3) | 1) + b"12345678"


def _fixed32_field(field_number: int) -> bytes:
    """Encode one fixed32 protobuf field."""
    return _varint((field_number << 3) | 5) + b"1234"


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


def test_classify_empty_success_payload_as_unknown() -> None:
    """Verify empty success envelopes are treated as unknown schema payloads."""
    response = Response()
    response.success.SetInParent()

    classification = classify_api_response_payload(response.SerializeToString())

    assert classification.kind == "unknown"
    assert classification.description == "unknown"


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
    assert "api_error code=10511" in classification.description


def test_format_api_error_payload_problem() -> None:
    """Verify API error diagnostics include title, body, and optional code."""
    payload = _api_error_payload(message="Plain upstream error")
    classification = classify_api_response_payload(payload)

    assert classification.kind == "api_error"
    assert "Invalid Parameter: Plain upstream error" in format_api_payload_problem(
        classification,
        context="title_index",
    )
    assert classification.error is not None
    assert classification.error.code is None


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


def test_extract_api_error_handles_non_matching_and_empty_error_branches() -> None:
    """Verify non-error and empty error branches do not produce application errors."""
    assert api_response.extract_api_error(_length_delimited_field(1, b"ignored")) is None
    assert api_response.extract_api_error(_length_delimited_field(2, b"")) is None


def test_extract_api_error_falls_back_to_first_localized_message() -> None:
    """Verify non-English-only envelopes still return a useful first message."""
    localized_error = _string_field(1, "Invalid Parameter") + _string_field(
        2,
        "Erreur amont sans anglais",
    )
    payload = _length_delimited_field(2, _length_delimited_field(5, localized_error))

    extracted = api_response.extract_api_error(payload)

    assert extracted is not None
    assert extracted.body == "Erreur amont sans anglais"


def test_private_error_helpers_handle_edge_values() -> None:
    """Cover defensive helper paths used by malformed upstream payloads."""

    class BadHasField:
        def HasField(self, _name: str) -> bool:
            raise ValueError("bad field")

    assert api_response._has_populated_success(BadHasField()) is False
    assert api_response._has_populated_success(Response()) is False
    assert api_response._extract_error_messages(_varint_field(1, 1)) == []
    assert api_response._parse_error_message(_length_delimited_field(5, b"Close")) is None
    assert api_response._looks_english("") is False
    assert api_response._decode_text(b"\xff") == ""


def test_raw_field_iterator_handles_malformed_wire_shapes() -> None:
    """Cover defensive wire parser branches for truncated/unsupported protobuf data."""
    assert api_response._iter_fields(b"", depth=99) == []
    assert api_response._iter_fields(b"\x80") == []
    assert api_response._iter_fields(_varint(1 << 3)) == []
    assert api_response._iter_fields(_varint((1 << 3) | 1)) == []
    assert api_response._iter_fields(_fixed64_field(1)) == [(1, 1, b"")]
    assert api_response._iter_fields(_varint((1 << 3) | 2)) == []
    assert api_response._iter_fields(_varint((1 << 3) | 2) + _varint(5) + b"ab") == []
    assert api_response._iter_fields(_varint((1 << 3) | 5)) == []
    assert api_response._iter_fields(_fixed32_field(1)) == [(1, 5, b"")]


def test_raw_varint_reader_rejects_invalid_values() -> None:
    """Verify low-level varint failures remain explicit for callers."""
    with pytest.raises(ValueError, match="varint too long"):
        api_response._read_varint(b"\x80" * 10, 0)

    with pytest.raises(ValueError, match="truncated varint"):
        api_response._read_varint(b"\x80", 0)
