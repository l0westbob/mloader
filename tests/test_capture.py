"""Tests for API payload capture persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mloader.manga_loader import capture as capture_module


def _varint(value: int) -> bytes:
    """Encode a protobuf varint for local error-envelope fixtures."""
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
    return _varint((field_number << 3) | 2) + _varint(len(value)) + value


def _string_field(field_number: int, value: str) -> bytes:
    """Encode one protobuf string field."""
    return _length_delimited_field(field_number, value.encode("utf-8"))


def _api_error_payload() -> bytes:
    """Build a minimal MangaPlus application-error envelope."""
    localized_error = _string_field(1, "Invalid Parameter") + _string_field(
        2,
        "There are issues connecting to Manga+. Please try again later.(10511)",
    )
    error_result = _length_delimited_field(2, localized_error)
    return _length_delimited_field(2, error_result)


def test_sanitize_filename_replaces_unsafe_characters() -> None:
    """Verify filename sanitizer removes unsupported filesystem characters."""
    assert capture_module._sanitize_filename(" chapter:/1 ") == "chapter_1"
    assert capture_module._sanitize_filename("...") == "capture"


def test_redact_params_masks_sensitive_keys() -> None:
    """Verify sensitive query values are replaced in metadata output."""
    params = {"a": 1, "secret": "abc", "Token": "xyz"}
    redacted = capture_module._redact_params(params)

    assert redacted["a"] == 1
    assert redacted["secret"] == "***REDACTED***"
    assert redacted["Token"] == "***REDACTED***"


def test_payload_capture_writes_raw_metadata_and_parsed_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify capture mode writes protobuf bytes, metadata, and parsed JSON."""

    class FakeResponse:
        @staticmethod
        def FromString(_payload: bytes) -> object:
            return object()

    monkeypatch.setattr(capture_module, "Response", FakeResponse)
    monkeypatch.setattr(capture_module, "MessageToDict", lambda _msg, **_kwargs: {"ok": True})

    recorder = capture_module.APIPayloadCapture(tmp_path)
    recorder.capture(
        endpoint="manga_viewer",
        identifier=123,
        url="https://api.example/api/manga_viewer",
        params={"chapter_id": 123, "secret": "hidden"},
        response_content=b"\x01\x02",
    )

    raw_files = sorted(tmp_path.glob("*.pb"))
    meta_files = sorted(tmp_path.glob("*.meta.json"))
    parsed_files = sorted(tmp_path.glob("*.response.json"))

    assert len(raw_files) == 1
    assert len(meta_files) == 1
    assert len(parsed_files) == 1

    metadata = json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert metadata["endpoint"] == "manga_viewer"
    assert metadata["identifier"] == "123"
    assert metadata["params"]["secret"] == "***REDACTED***"
    assert metadata["payload_classification"] == "unknown"
    assert metadata["parsed_payload_file"] == parsed_files[0].name
    assert raw_files[0].read_bytes() == b"\x01\x02"

    parsed = json.loads(parsed_files[0].read_text(encoding="utf-8"))
    assert parsed == {"ok": True}


def test_payload_capture_records_parse_error_without_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify parse failures still keep raw payload and metadata."""

    class FakeResponse:
        @staticmethod
        def FromString(_payload: bytes) -> object:
            raise ValueError("bad payload")

    monkeypatch.setattr(capture_module, "Response", FakeResponse)

    recorder = capture_module.APIPayloadCapture(tmp_path)
    recorder.capture(
        endpoint="title_detailV3",
        identifier="foo",
        url="https://api.example/api/title_detailV3",
        params={"title_id": 7},
        response_content=b"\x09",
    )

    meta_files = sorted(tmp_path.glob("*.meta.json"))
    assert len(meta_files) == 1
    assert list(tmp_path.glob("*.response.json")) == []

    metadata = json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert metadata["endpoint"] == "title_detailV3"
    assert "parsed_payload_error" in metadata


def test_payload_capture_records_api_error_metadata(tmp_path: Path) -> None:
    """Verify captured MangaPlus error envelopes are described in metadata."""
    recorder = capture_module.APIPayloadCapture(tmp_path)
    recorder.capture(
        endpoint="title_index",
        identifier="all",
        url="https://api.example/api/title_list/allV2",
        params={"secret": "hidden"},
        response_content=_api_error_payload(),
    )

    metadata = json.loads(next(tmp_path.glob("*.meta.json")).read_text(encoding="utf-8"))

    assert metadata["payload_classification"] == "api_error"
    assert metadata["api_error"]["title"] == "Invalid Parameter"
    assert metadata["api_error"]["code"] == "10511"
