"""Verification entrypoints for recorded API capture payloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mloader.infrastructure.mangaplus.api_response import classify_api_response_payload
from mloader.infrastructure.mangaplus.capture_metadata import (
    CapturePayload,
    CaptureVerificationError,
    load_capture_payload,
)
from mloader.infrastructure.mangaplus.capture_payload_validation import (
    verify_manga_viewer_payload,
    verify_title_detail_payload,
    verify_title_index_payload,
)
from mloader.infrastructure.mangaplus.capture_signatures import (
    build_api_error_signature,
    build_schema_signature,
)
from mloader.response_pb2 import Response


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


def _record_signature(capture: CapturePayload) -> _CaptureRecord:
    """Validate one capture payload and return its baseline signature."""
    classification = classify_api_response_payload(capture.payload)
    if classification.kind == "api_error":
        return _CaptureRecord(
            stem=capture.stem,
            endpoint=capture.endpoint,
            signature_json=build_api_error_signature(
                endpoint=capture.endpoint,
                metadata=capture.metadata,
                classification=classification,
            ),
        )

    parsed = Response.FromString(capture.payload)
    if not parsed.HasField("success"):
        raise CaptureVerificationError(f"Missing success envelope in {capture.raw_payload_file}")

    if capture.endpoint == "title_detailV3":
        verify_title_detail_payload(parsed, capture.stem)
    elif capture.endpoint == "manga_viewer":
        verify_manga_viewer_payload(parsed, capture.stem, metadata=capture.metadata)
    elif capture.endpoint == "title_index":
        verify_title_index_payload(parsed, capture.stem)

    return _CaptureRecord(
        stem=capture.stem,
        endpoint=capture.endpoint,
        signature_json=build_schema_signature(
            endpoint=capture.endpoint,
            metadata=capture.metadata,
            parsed=parsed,
        ),
    )


def _verify_capture_schema_records(
    capture_dir_path: Path,
) -> tuple[CaptureVerificationSummary, list[_CaptureRecord]]:
    """Verify capture directory and return summary with per-record signatures."""
    if not capture_dir_path.exists() or not capture_dir_path.is_dir():
        raise CaptureVerificationError(f"Capture directory not found: {capture_dir_path}")

    meta_paths = sorted(capture_dir_path.glob("*.meta.json"))
    if not meta_paths:
        raise CaptureVerificationError(f"No '*.meta.json' files found in: {capture_dir_path}")

    endpoint_counts: dict[str, int] = {}
    records: list[_CaptureRecord] = []
    for meta_path in meta_paths:
        capture = load_capture_payload(capture_dir_path, meta_path)
        records.append(_record_signature(capture))
        endpoint_counts[capture.endpoint] = endpoint_counts.get(capture.endpoint, 0) + 1

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
