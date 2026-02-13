"""Tests for API payload capture persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mloader.manga_loader import capture as capture_module


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
