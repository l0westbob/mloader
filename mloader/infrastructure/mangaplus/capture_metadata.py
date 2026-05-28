"""Capture metadata loading and payload integrity checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

SUPPORTED_ENDPOINTS = frozenset({"manga_viewer", "title_detailV3", "title_index"})


class CaptureVerificationError(ValueError):
    """Raised when a capture set fails schema verification."""


@dataclass(frozen=True)
class CapturePayload:
    """Raw capture payload with validated metadata."""

    stem: str
    endpoint: str
    metadata: dict[str, Any]
    payload: bytes
    raw_payload_file: str


def load_metadata(meta_path: Path) -> dict[str, Any]:
    """Load and return metadata JSON as a dictionary."""
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise CaptureVerificationError(f"Metadata file is not an object: {meta_path}")
    return cast(dict[str, Any], metadata)


def load_capture_payload(capture_dir_path: Path, meta_path: Path) -> CapturePayload:
    """Load capture metadata and verify the referenced raw payload."""
    metadata = load_metadata(meta_path)
    stem = meta_path.name.removesuffix(".meta.json")

    endpoint = str(metadata.get("endpoint", ""))
    if not endpoint:
        raise CaptureVerificationError(f"Missing endpoint in metadata file: {meta_path.name}")
    if endpoint not in SUPPORTED_ENDPOINTS:
        raise CaptureVerificationError(
            f"Unsupported endpoint '{endpoint}' in metadata {meta_path.name}"
        )

    raw_payload_file = str(metadata.get("raw_payload_file", f"{stem}.pb"))
    raw_payload_path = capture_dir_path / raw_payload_file
    if not raw_payload_path.exists():
        raise CaptureVerificationError(
            f"Missing raw payload file referenced by metadata: {raw_payload_file}"
        )

    payload = raw_payload_path.read_bytes()
    payload_size = metadata.get("payload_size_bytes")
    if isinstance(payload_size, int) and payload_size != len(payload):
        raise CaptureVerificationError(
            f"Payload size mismatch for {raw_payload_file}: "
            f"metadata={payload_size}, actual={len(payload)}"
        )

    payload_sha = metadata.get("payload_sha256")
    if isinstance(payload_sha, str) and payload_sha != sha256(payload).hexdigest():
        raise CaptureVerificationError(f"Payload sha256 mismatch for {raw_payload_file}")

    return CapturePayload(
        stem=stem,
        endpoint=endpoint,
        metadata=metadata,
        payload=payload,
        raw_payload_file=raw_payload_file,
    )
