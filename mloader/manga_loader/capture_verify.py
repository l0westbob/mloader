"""Verification helpers for recorded API capture payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from google.protobuf.json_format import MessageToDict
from mloader.response_pb2 import Response  # type: ignore


class CaptureVerificationError(ValueError):
    """Raised when a capture set fails schema verification."""


@dataclass(frozen=True)
class CaptureVerificationSummary:
    """Summary produced after capture schema verification."""

    total_records: int
    endpoint_counts: dict[str, int]


@dataclass(frozen=True)
class _CaptureRecord:
    """Internal verified capture record used for baseline comparison."""

    stem: str
    endpoint: str
    signature_json: str


def _load_metadata(meta_path: Path) -> dict[str, Any]:
    """Load and return metadata JSON as a dictionary."""
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise CaptureVerificationError(f"Metadata file is not an object: {meta_path}")
    return metadata


def _as_dict(value: object, context: str) -> dict[str, Any]:
    """Return ``value`` as dictionary or raise descriptive verification error."""
    if not isinstance(value, dict):
        raise CaptureVerificationError(f"Expected object at {context}")
    return value


def _as_list(value: object, context: str) -> list[Any]:
    """Return ``value`` as list or raise descriptive verification error."""
    if not isinstance(value, list):
        raise CaptureVerificationError(f"Expected list at {context}")
    return value


def _build_schema_signature(
    *,
    endpoint: str,
    metadata: dict[str, Any],
    parsed: Response,
) -> str:
    """Build normalized schema signature JSON for baseline drift checks."""
    response_data = MessageToDict(
        parsed,
        preserving_proto_field_name=True,
        use_integers_for_enums=True,
    )
    success = _as_dict(response_data.get("success"), "response.success")
    params = _as_dict(metadata.get("params"), "metadata.params")

    signature: dict[str, object] = {
        "endpoint": endpoint,
        "url_path": urlparse(str(metadata.get("url", ""))).path,
        "meta_keys": sorted(metadata.keys()),
        "param_keys": sorted(params.keys()),
        "success_keys": sorted(success.keys()),
    }

    if endpoint == "manga_viewer":
        viewer = _as_dict(success.get("manga_viewer"), "response.success.manga_viewer")
        signature["payload_keys"] = sorted(viewer.keys())

        pages = _as_list(viewer.get("pages"), "response.success.manga_viewer.pages")
        if not pages:
            raise CaptureVerificationError("Expected at least one page in response.success.manga_viewer.pages")
        first_page = _as_dict(pages[0], "response.success.manga_viewer.pages[0]")
        last_page = _as_dict(pages[-1], "response.success.manga_viewer.pages[-1]")
        signature["first_page_keys"] = sorted(first_page.keys())
        signature["last_page_keys"] = sorted(last_page.keys())
        signature["manga_page_keys"] = sorted(
            _as_dict(first_page.get("manga_page"), "response.success.manga_viewer.pages[0].manga_page").keys()
        )
        signature["last_page_payload_keys"] = sorted(
            _as_dict(last_page.get("last_page"), "response.success.manga_viewer.pages[-1].last_page").keys()
        )
        return json.dumps(signature, sort_keys=True)

    if endpoint == "title_detailV3":
        title_detail = _as_dict(success.get("title_detail_view"), "response.success.title_detail_view")
        signature["payload_keys"] = sorted(title_detail.keys())
        signature["title_keys"] = sorted(
            _as_dict(title_detail.get("title"), "response.success.title_detail_view.title").keys()
        )

        chapter_groups = _as_list(
            title_detail.get("chapter_list_group"),
            "response.success.title_detail_view.chapter_list_group",
        )
        if not chapter_groups:
            raise CaptureVerificationError(
                "Expected at least one group in response.success.title_detail_view.chapter_list_group"
            )
        first_group = _as_dict(
            chapter_groups[0],
            "response.success.title_detail_view.chapter_list_group[0]",
        )
        signature["chapter_group_keys"] = sorted(first_group.keys())

        first_chapter_list = _as_list(
            first_group.get("first_chapter_list"),
            "response.success.title_detail_view.chapter_list_group[0].first_chapter_list",
        )
        if not first_chapter_list:
            raise CaptureVerificationError(
                "Expected at least one chapter in first_chapter_list for response.success.title_detail_view"
            )
        first_chapter = _as_dict(
            first_chapter_list[0],
            "response.success.title_detail_view.chapter_list_group[0].first_chapter_list[0]",
        )
        signature["chapter_keys"] = sorted(first_chapter.keys())
        return json.dumps(signature, sort_keys=True)

    raise CaptureVerificationError(f"Unsupported endpoint '{endpoint}'")


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


def _verify_capture_schema_records(capture_dir_path: Path) -> tuple[CaptureVerificationSummary, list[_CaptureRecord]]:
    """Verify capture directory and return summary with per-record signatures."""
    if not capture_dir_path.exists() or not capture_dir_path.is_dir():
        raise CaptureVerificationError(f"Capture directory not found: {capture_dir_path}")

    meta_paths = sorted(capture_dir_path.glob("*.meta.json"))
    if not meta_paths:
        raise CaptureVerificationError(f"No '*.meta.json' files found in: {capture_dir_path}")

    endpoint_counts: dict[str, int] = {}
    records: list[_CaptureRecord] = []
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

        records.append(
            _CaptureRecord(
                stem=stem,
                endpoint=endpoint,
                signature_json=_build_schema_signature(endpoint=endpoint, metadata=metadata, parsed=parsed),
            )
        )
        endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

    summary = CaptureVerificationSummary(
        total_records=sum(endpoint_counts.values()),
        endpoint_counts=endpoint_counts,
    )
    return summary, records


def verify_capture_schema(capture_dir: str | Path) -> CaptureVerificationSummary:
    """Verify capture metadata + protobuf payloads against required runtime fields."""
    summary, _records = _verify_capture_schema_records(Path(capture_dir))
    return summary


def verify_capture_schema_against_baseline(
    capture_dir: str | Path,
    baseline_dir: str | Path,
) -> CaptureVerificationSummary:
    """Verify captures and compare structural signatures against a baseline set."""
    capture_summary, capture_records = _verify_capture_schema_records(Path(capture_dir))
    _baseline_summary, baseline_records = _verify_capture_schema_records(Path(baseline_dir))

    baseline_by_endpoint: dict[str, set[str]] = {}
    for record in baseline_records:
        baseline_by_endpoint.setdefault(record.endpoint, set()).add(record.signature_json)

    for record in capture_records:
        if record.endpoint not in baseline_by_endpoint:
            raise CaptureVerificationError(
                f"Unknown endpoint '{record.endpoint}' in capture '{record.stem}' compared to baseline"
            )
        if record.signature_json not in baseline_by_endpoint[record.endpoint]:
            raise CaptureVerificationError(
                f"Schema drift detected for capture '{record.stem}' endpoint '{record.endpoint}' "
                f"when compared to baseline '{baseline_dir}'"
            )
    return capture_summary
