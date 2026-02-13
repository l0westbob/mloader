"""Verification helpers for recorded API capture payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from mloader.response_pb2 import Response  # type: ignore


class CaptureVerificationError(ValueError):
    """Raised when a capture set fails schema verification."""


@dataclass(frozen=True)
class CaptureVerificationSummary:
    """Summary produced after capture schema verification."""

    total_records: int
    endpoint_counts: dict[str, int]


def _load_metadata(meta_path: Path) -> dict[str, Any]:
    """Load and return metadata JSON as a dictionary."""
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise CaptureVerificationError(f"Metadata file is not an object: {meta_path}")
    return metadata


def _verify_title_detail_payload(parsed: Response, stem: str) -> None:
    """Validate required title-detail fields used by planner/download flow."""
    if not parsed.success.HasField("title_detail_view"):
        raise CaptureVerificationError(f"Missing success.title_detail_view in {stem}.pb")

    title_detail = parsed.success.title_detail_view
    if title_detail.title.title_id == 0 or not title_detail.title.name:
        raise CaptureVerificationError(f"Missing required title identity fields in {stem}.pb")

    if not title_detail.chapter_list_group:
        raise CaptureVerificationError(f"No chapter_list_group records in {stem}.pb")

    has_any_chapter = any(
        group.first_chapter_list or group.mid_chapter_list or group.last_chapter_list
        for group in title_detail.chapter_list_group
    )
    if not has_any_chapter:
        raise CaptureVerificationError(f"No chapter entries found in chapter_list_group for {stem}.pb")


def _verify_manga_viewer_payload(parsed: Response, stem: str) -> None:
    """Validate required manga-viewer fields used by download flow."""
    if not parsed.success.HasField("manga_viewer"):
        raise CaptureVerificationError(f"Missing success.manga_viewer in {stem}.pb")

    viewer = parsed.success.manga_viewer
    if viewer.title_id == 0 or viewer.chapter_id == 0:
        raise CaptureVerificationError(f"Missing viewer title_id/chapter_id fields in {stem}.pb")

    if not viewer.pages:
        raise CaptureVerificationError(f"No pages found in manga_viewer payload {stem}.pb")

    if not any(page.manga_page.image_url for page in viewer.pages):
        raise CaptureVerificationError(f"No manga_page.image_url found in pages for {stem}.pb")

    last_page = viewer.pages[-1].last_page
    if last_page.current_chapter.chapter_id == 0:
        raise CaptureVerificationError(f"Missing last_page.current_chapter in {stem}.pb")


def verify_capture_schema(capture_dir: str | Path) -> CaptureVerificationSummary:
    """Verify capture metadata + protobuf payloads against required runtime fields."""
    capture_dir_path = Path(capture_dir)
    if not capture_dir_path.exists() or not capture_dir_path.is_dir():
        raise CaptureVerificationError(f"Capture directory not found: {capture_dir_path}")

    meta_paths = sorted(capture_dir_path.glob("*.meta.json"))
    if not meta_paths:
        raise CaptureVerificationError(f"No '*.meta.json' files found in: {capture_dir_path}")

    endpoint_counts: dict[str, int] = {}
    for meta_path in meta_paths:
        metadata = _load_metadata(meta_path)
        stem = meta_path.name.removesuffix(".meta.json")

        endpoint = str(metadata.get("endpoint", ""))
        if not endpoint:
            raise CaptureVerificationError(f"Missing endpoint in metadata file: {meta_path.name}")

        raw_payload_file = str(metadata.get("raw_payload_file", f"{stem}.pb"))
        raw_payload_path = capture_dir_path / raw_payload_file
        if not raw_payload_path.exists():
            raise CaptureVerificationError(f"Missing raw payload file referenced by metadata: {raw_payload_file}")

        payload = raw_payload_path.read_bytes()
        payload_size = metadata.get("payload_size_bytes")
        if isinstance(payload_size, int) and payload_size != len(payload):
            raise CaptureVerificationError(
                f"Payload size mismatch for {raw_payload_file}: metadata={payload_size}, actual={len(payload)}"
            )

        payload_sha = metadata.get("payload_sha256")
        if isinstance(payload_sha, str) and payload_sha != sha256(payload).hexdigest():
            raise CaptureVerificationError(f"Payload sha256 mismatch for {raw_payload_file}")

        parsed = Response.FromString(payload)
        if not parsed.HasField("success"):
            raise CaptureVerificationError(f"Missing success envelope in {raw_payload_file}")

        if endpoint == "title_detailV3":
            _verify_title_detail_payload(parsed, stem)
        elif endpoint == "manga_viewer":
            _verify_manga_viewer_payload(parsed, stem)
        else:
            raise CaptureVerificationError(f"Unsupported endpoint '{endpoint}' in metadata {meta_path.name}")

        endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

    return CaptureVerificationSummary(
        total_records=sum(endpoint_counts.values()),
        endpoint_counts=endpoint_counts,
    )
