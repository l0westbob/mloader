"""Tests for capture verification against required response fields."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from mloader.manga_loader.capture_verify import (
    CaptureVerificationError,
    _as_dict,
    _as_list,
    _build_schema_signature,
    _load_metadata,
    _verify_manga_viewer_payload,
    _verify_title_detail_payload,
    verify_capture_schema_against_baseline,
    verify_capture_schema,
)
from mloader.response_pb2 import Response  # type: ignore

FIXTURE_CAPTURE_DIR = Path(__file__).parent / "fixtures" / "api_captures" / "baseline"


def _copy_fixture_set(target_dir: Path) -> None:
    """Copy baseline capture fixture files into ``target_dir``."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for fixture_file in FIXTURE_CAPTURE_DIR.iterdir():
        if fixture_file.is_file():
            (target_dir / fixture_file.name).write_bytes(fixture_file.read_bytes())


def _update_payload_metadata(meta_path: Path, payload: bytes) -> None:
    """Update metadata checksums/size after payload mutation."""
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["payload_size_bytes"] = len(payload)
    metadata["payload_sha256"] = sha256(payload).hexdigest()
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def test_verify_capture_schema_with_real_fixture_set() -> None:
    """Verify baseline fixture set passes schema verification."""
    summary = verify_capture_schema(FIXTURE_CAPTURE_DIR)

    assert summary.total_records == 3
    assert summary.endpoint_counts == {"manga_viewer": 2, "title_detailV3": 1}


def test_verify_capture_schema_against_baseline_with_real_fixture_set() -> None:
    """Verify baseline comparison passes for matching capture and baseline sets."""
    summary = verify_capture_schema_against_baseline(FIXTURE_CAPTURE_DIR, FIXTURE_CAPTURE_DIR)
    assert summary.total_records == 3


def test_verify_capture_schema_against_baseline_detects_drift(tmp_path: Path) -> None:
    """Verify baseline comparison fails when capture signature keys drift."""
    _copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0002_manga_viewer_1000311.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["params"]["extra_param"] = "1"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Schema drift detected"):
        verify_capture_schema_against_baseline(tmp_path, FIXTURE_CAPTURE_DIR)


def test_verify_capture_schema_against_baseline_rejects_unknown_capture_endpoint(
    tmp_path: Path,
) -> None:
    """Verify comparison fails when capture has endpoint absent from baseline set."""
    capture_dir = tmp_path / "capture"
    baseline_dir = tmp_path / "baseline"
    _copy_fixture_set(capture_dir)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    for fixture_file in FIXTURE_CAPTURE_DIR.glob("0001_title_detailV3_100010.*"):
        (baseline_dir / fixture_file.name).write_bytes(fixture_file.read_bytes())

    with pytest.raises(CaptureVerificationError, match="Unknown endpoint"):
        verify_capture_schema_against_baseline(capture_dir, baseline_dir)


def test_verify_capture_schema_fails_without_metadata_files(tmp_path: Path) -> None:
    """Verify verifier fails when capture directory has no metadata records."""
    with pytest.raises(CaptureVerificationError, match="No '\\*\\.meta\\.json' files found"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_unsupported_endpoint(tmp_path: Path) -> None:
    """Verify verifier rejects unknown endpoint names in metadata."""
    _copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["endpoint"] = "unsupported_endpoint"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Unsupported endpoint"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_size_mismatch(tmp_path: Path) -> None:
    """Verify verifier catches payload size mismatches from metadata."""
    _copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0002_manga_viewer_1000311.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["payload_size_bytes"] = 1
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Payload size mismatch"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_sha_mismatch(tmp_path: Path) -> None:
    """Verify verifier catches payload checksum mismatches from metadata."""
    _copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0002_manga_viewer_1000311.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["payload_sha256"] = "0" * 64
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Payload sha256 mismatch"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_manga_viewer_missing_pages(tmp_path: Path) -> None:
    """Verify verifier rejects manga_viewer payloads with empty pages."""
    _copy_fixture_set(tmp_path)

    payload_path = tmp_path / "0002_manga_viewer_1000311.pb"
    parsed = Response.FromString(payload_path.read_bytes())
    parsed.success.manga_viewer.ClearField("pages")
    mutated_payload = parsed.SerializeToString()
    payload_path.write_bytes(mutated_payload)

    meta_path = tmp_path / "0002_manga_viewer_1000311.meta.json"
    _update_payload_metadata(meta_path, mutated_payload)

    with pytest.raises(CaptureVerificationError, match="No pages found in manga_viewer payload"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_title_detail_missing_groups(tmp_path: Path) -> None:
    """Verify verifier rejects title_detail payloads with no chapter groups."""
    _copy_fixture_set(tmp_path)

    payload_path = tmp_path / "0001_title_detailV3_100010.pb"
    parsed = Response.FromString(payload_path.read_bytes())
    parsed.success.title_detail_view.ClearField("chapter_list_group")
    mutated_payload = parsed.SerializeToString()
    payload_path.write_bytes(mutated_payload)

    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    _update_payload_metadata(meta_path, mutated_payload)

    with pytest.raises(CaptureVerificationError, match="No chapter_list_group records"):
        verify_capture_schema(tmp_path)


def test_load_metadata_rejects_non_dict_json(tmp_path: Path) -> None:
    """Verify metadata loader requires a JSON object."""
    meta_path = tmp_path / "record.meta.json"
    meta_path.write_text("[]", encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Metadata file is not an object"):
        _load_metadata(meta_path)


def test_verify_capture_schema_fails_for_missing_directory() -> None:
    """Verify verifier rejects nonexistent capture directories."""
    with pytest.raises(CaptureVerificationError, match="Capture directory not found"):
        verify_capture_schema("does-not-exist")


def test_verify_capture_schema_fails_for_missing_endpoint(tmp_path: Path) -> None:
    """Verify verifier rejects metadata without endpoint values."""
    _copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["endpoint"] = ""
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Missing endpoint"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_missing_raw_payload_reference(tmp_path: Path) -> None:
    """Verify verifier rejects metadata pointing to missing raw payload files."""
    _copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["raw_payload_file"] = "missing.pb"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Missing raw payload file referenced by metadata"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_missing_success_envelope(tmp_path: Path) -> None:
    """Verify verifier rejects payloads without a success envelope."""
    capture_name = "0001_title_detailV3_100010"
    payload_path = tmp_path / f"{capture_name}.pb"
    payload_path.write_bytes(b"")

    metadata = {
        "endpoint": "title_detailV3",
        "raw_payload_file": payload_path.name,
        "payload_size_bytes": 0,
        "payload_sha256": sha256(b"").hexdigest(),
    }
    (tmp_path / f"{capture_name}.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(CaptureVerificationError, match="Missing success envelope"):
        verify_capture_schema(tmp_path)


def test_verify_title_detail_payload_rejects_missing_title_detail() -> None:
    """Verify title-detail payload verifier rejects missing payload branch."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    parsed.success.manga_viewer.chapter_id = 1024959
    with pytest.raises(CaptureVerificationError, match="Missing success.title_detail_view"):
        _verify_title_detail_payload(parsed, "sample")


def test_verify_title_detail_payload_rejects_missing_title_identity() -> None:
    """Verify title-detail payload verifier requires title identity fields."""
    parsed = Response()
    parsed.success.title_detail_view.chapter_list_group.add()
    with pytest.raises(CaptureVerificationError, match="Missing required title identity fields"):
        _verify_title_detail_payload(parsed, "sample")


def test_verify_title_detail_payload_rejects_empty_chapter_groups() -> None:
    """Verify title-detail payload verifier rejects groups without chapters."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100312
    parsed.success.title_detail_view.title.name = "T"
    parsed.success.title_detail_view.chapter_list_group.add()
    with pytest.raises(CaptureVerificationError, match="No chapter entries found in chapter_list_group"):
        _verify_title_detail_payload(parsed, "sample")


def test_verify_manga_viewer_payload_rejects_missing_viewer() -> None:
    """Verify manga-viewer payload verifier rejects missing payload branch."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100312
    parsed.success.title_detail_view.title.name = "T"
    with pytest.raises(CaptureVerificationError, match="Missing success.manga_viewer"):
        _verify_manga_viewer_payload(parsed, "sample")


def test_verify_manga_viewer_payload_rejects_missing_ids() -> None:
    """Verify manga-viewer payload verifier requires non-zero identity fields."""
    parsed = Response()
    parsed.success.manga_viewer.pages.add().manga_page.image_url = "http://img"
    with pytest.raises(CaptureVerificationError, match="Missing viewer title_id/chapter_id fields"):
        _verify_manga_viewer_payload(parsed, "sample")


def test_verify_manga_viewer_payload_rejects_missing_image_urls() -> None:
    """Verify manga-viewer payload verifier requires at least one image URL."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    parsed.success.manga_viewer.chapter_id = 1024959
    parsed.success.manga_viewer.pages.add()
    with pytest.raises(CaptureVerificationError, match="No manga_page.image_url found in pages"):
        _verify_manga_viewer_payload(parsed, "sample")


def test_verify_manga_viewer_payload_rejects_missing_last_page_chapter() -> None:
    """Verify manga-viewer payload verifier requires terminal chapter linkage."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    parsed.success.manga_viewer.chapter_id = 1024959
    page = parsed.success.manga_viewer.pages.add()
    page.manga_page.image_url = "http://img"
    with pytest.raises(CaptureVerificationError, match="Missing last_page.current_chapter"):
        _verify_manga_viewer_payload(parsed, "sample")


def test_build_schema_signature_rejects_unknown_endpoint() -> None:
    """Verify schema-signature builder rejects unsupported endpoint names."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100312
    parsed.success.title_detail_view.title.name = "title"
    group = parsed.success.title_detail_view.chapter_list_group.add()
    group.first_chapter_list.add().chapter_id = 1024959
    with pytest.raises(CaptureVerificationError, match="Unsupported endpoint"):
        _build_schema_signature(
            endpoint="unknown",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=parsed,
        )


def test_as_dict_rejects_non_dict() -> None:
    """Verify dict coercion helper rejects non-object values."""
    with pytest.raises(CaptureVerificationError, match="Expected object at"):
        _as_dict([], "ctx")


def test_as_list_rejects_non_list() -> None:
    """Verify list coercion helper rejects non-list values."""
    with pytest.raises(CaptureVerificationError, match="Expected list at"):
        _as_list({}, "ctx")


def test_build_schema_signature_rejects_empty_pages_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects manga_viewer payloads with explicit empty pages list."""
    monkeypatch.setattr(
        "mloader.manga_loader.capture_verify.MessageToDict",
        lambda *_args, **_kwargs: {"success": {"manga_viewer": {"pages": []}}},
    )

    with pytest.raises(CaptureVerificationError, match="Expected at least one page"):
        _build_schema_signature(
            endpoint="manga_viewer",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=Response(),
        )


def test_build_schema_signature_rejects_empty_title_detail_group_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects title_detail payloads with no groups."""
    monkeypatch.setattr(
        "mloader.manga_loader.capture_verify.MessageToDict",
        lambda *_args, **_kwargs: {"success": {"title_detail_view": {"title": {}, "chapter_list_group": []}}},
    )

    with pytest.raises(CaptureVerificationError, match="Expected at least one group"):
        _build_schema_signature(
            endpoint="title_detailV3",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=Response(),
        )


def test_build_schema_signature_rejects_empty_first_chapter_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects title_detail payloads with empty first_chapter_list."""
    monkeypatch.setattr(
        "mloader.manga_loader.capture_verify.MessageToDict",
        lambda *_args, **_kwargs: {
            "success": {
                "title_detail_view": {
                    "title": {},
                    "chapter_list_group": [{"first_chapter_list": []}],
                }
            }
        },
    )

    with pytest.raises(CaptureVerificationError, match="Expected at least one chapter in first_chapter_list"):
        _build_schema_signature(
            endpoint="title_detailV3",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=Response(),
        )
