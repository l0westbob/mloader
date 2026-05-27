"""Shared helpers for capture verification tests."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

FIXTURE_CAPTURE_DIR = Path(__file__).parent / "fixtures" / "api_captures" / "baseline"


def copy_fixture_set(target_dir: Path) -> None:
    """Copy baseline capture fixture files into ``target_dir``."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for fixture_file in FIXTURE_CAPTURE_DIR.iterdir():
        if fixture_file.is_file():
            (target_dir / fixture_file.name).write_bytes(fixture_file.read_bytes())


def update_payload_metadata(meta_path: Path, payload: bytes) -> None:
    """Update metadata checksums/size after payload mutation."""
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["payload_size_bytes"] = len(payload)
    metadata["payload_sha256"] = sha256(payload).hexdigest()
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _varint_field(field_number: int, value: int) -> bytes:
    """Encode one varint protobuf field."""
    return _varint(field_number << 3) + _varint(value)


def _string_field(field_number: int, value: str) -> bytes:
    """Encode one protobuf string field."""
    return _length_delimited_field(field_number, value.encode("utf-8"))


def api_error_payload() -> bytes:
    """Build a minimal MangaPlus application-error envelope."""
    localized_error = (
        _string_field(1, "Invalid Parameter")
        + _string_field(
            2,
            "There are issues connecting to Manga+. Please try again later.(10511)",
        )
        + _varint_field(6, 0)
    )
    error_result = _length_delimited_field(2, localized_error)
    return _length_delimited_field(2, error_result)
