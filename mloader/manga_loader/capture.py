"""API payload capture helpers for reproducible fixture generation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha256
from itertools import count
from pathlib import Path
from typing import Mapping

from google.protobuf.json_format import MessageToDict

from mloader.response_pb2 import Response  # type: ignore

_FILENAME_SANITIZER = re.compile(r"[^a-zA-Z0-9_.-]+")
_REDACTED_PARAM_KEYS = frozenset(
    {
        "secret",
        "authorization",
        "auth",
        "token",
        "cookie",
        "session",
    }
)


def _sanitize_filename(value: str) -> str:
    """Return a filesystem-safe slug for capture file names."""
    sanitized = _FILENAME_SANITIZER.sub("_", value.strip())
    return sanitized.strip("._") or "capture"


def _redact_params(params: Mapping[str, object]) -> dict[str, object]:
    """Return a sorted parameter mapping with sensitive values redacted."""
    redacted: dict[str, object] = {}
    for key, value in sorted(params.items(), key=lambda item: item[0]):
        redacted[key] = "***REDACTED***" if key.lower() in _REDACTED_PARAM_KEYS else value
    return redacted


class APIPayloadCapture:
    """Persist raw and parsed API payloads for later regression analysis."""

    def __init__(self, capture_dir: str | Path) -> None:
        """Initialize capture directory and sequence counter."""
        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self._sequence = count(1)

    def capture(
        self,
        *,
        endpoint: str,
        identifier: str | int,
        url: str,
        params: Mapping[str, object],
        response_content: bytes,
    ) -> None:
        """Write capture metadata, raw protobuf payload, and optional parsed JSON."""
        sequence = next(self._sequence)
        capture_stem = (
            f"{sequence:04d}_{_sanitize_filename(endpoint)}_{_sanitize_filename(str(identifier))}"
        )
        raw_payload_path = self.capture_dir / f"{capture_stem}.pb"
        metadata_path = self.capture_dir / f"{capture_stem}.meta.json"
        parsed_response_path = self.capture_dir / f"{capture_stem}.response.json"

        raw_payload_path.write_bytes(response_content)

        metadata: dict[str, object] = {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "identifier": str(identifier),
            "url": url,
            "params": _redact_params(params),
            "payload_sha256": sha256(response_content).hexdigest(),
            "payload_size_bytes": len(response_content),
            "raw_payload_file": raw_payload_path.name,
        }

        try:
            parsed_response = Response.FromString(response_content)
            parsed_dict = MessageToDict(
                parsed_response,
                preserving_proto_field_name=True,
                use_integers_for_enums=True,
            )
        except Exception as exc:
            metadata["parsed_payload_error"] = str(exc)
        else:
            parsed_response_path.write_text(
                json.dumps(parsed_dict, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            metadata["parsed_payload_file"] = parsed_response_path.name

        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
