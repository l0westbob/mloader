"""Tests for capture verification against required response fields."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from mloader.infrastructure.mangaplus.capture_metadata import (
    CaptureVerificationError,
    load_metadata,
)
from mloader.infrastructure.mangaplus.capture_verify import (
    verify_capture_schema_against_baseline,
    verify_capture_schema,
)
from mloader.response_pb2 import Response
from tests.capture_verify_helpers import (
    FIXTURE_CAPTURE_DIR,
    api_error_payload,
    copy_fixture_set,
    update_payload_metadata,
)


def test_verify_capture_schema_with_real_fixture_set() -> None:
    """Verify baseline fixture set passes schema verification."""
    summary = verify_capture_schema(FIXTURE_CAPTURE_DIR)

    assert summary.total_records == 8
    assert summary.endpoint_counts == {
        "manga_viewer": 4,
        "title_detailV3": 2,
        "title_index": 2,
    }


def test_baseline_fixture_set_covers_api_drift_cases() -> None:
    """Verify checked-in baseline captures include the known MangaPlus drift shapes."""
    fixture_names = {path.name for path in FIXTURE_CAPTURE_DIR.glob("*.meta.json")}
    assert "0004_title_index_all.meta.json" in fixture_names
    assert "0005_title_detailV3_flat_chapter_list.meta.json" in fixture_names
    assert "0006_title_index_api_error.meta.json" in fixture_names
    assert "0007_manga_viewer_subscription_required.meta.json" in fixture_names
    assert "0008_manga_viewer_encrypted_page.meta.json" in fixture_names

    flat_title_detail = json.loads(
        (FIXTURE_CAPTURE_DIR / "0005_title_detailV3_flat_chapter_list.response.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        flat_title_detail["success"]["title_detail_view"]["chapter_list"][0]["chapter_id"]
        == 1024974
    )

    encrypted_viewer = json.loads(
        (FIXTURE_CAPTURE_DIR / "0008_manga_viewer_encrypted_page.response.json").read_text(
            encoding="utf-8"
        )
    )
    encrypted_page = encrypted_viewer["success"]["manga_viewer"]["pages"][0]["manga_page"]
    assert encrypted_page["encryption_key"] == "00112233445566778899aabbccddeeff"

    subscription_meta = json.loads(
        (FIXTURE_CAPTURE_DIR / "0007_manga_viewer_subscription_required.meta.json").read_text(
            encoding="utf-8"
        )
    )
    assert subscription_meta["expected_runtime_error"] == "subscription_required"


def test_verify_capture_schema_accepts_api_error_envelope(tmp_path: Path) -> None:
    """Verify captured MangaPlus application errors are first-class fixtures."""
    payload = api_error_payload()
    payload_path = tmp_path / "0001_title_index_all.pb"
    payload_path.write_bytes(payload)
    metadata = {
        "endpoint": "title_index",
        "identifier": "all",
        "url": "https://jumpg-webapi.tokyo-cdn.com/api/title_list/allV2",
        "params": {"id_length": 6},
        "raw_payload_file": payload_path.name,
        "payload_size_bytes": len(payload),
        "payload_sha256": sha256(payload).hexdigest(),
        "payload_classification": "api_error",
        "api_error": {
            "title": "Invalid Parameter",
            "body": "There are issues connecting to Manga+. Please try again later.(10511)",
            "code": "10511",
            "language": 0,
        },
    }
    (tmp_path / "0001_title_index_all.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = verify_capture_schema(tmp_path)

    assert summary.total_records == 1
    assert summary.endpoint_counts == {"title_index": 1}


def test_verify_capture_schema_accepts_title_index_success_payload(tmp_path: Path) -> None:
    """Verify title-index success captures are validated and counted."""
    parsed = Response()
    group = parsed.success.all_titles_view.title_groups.add()
    group.group_name = "weekly"
    title = group.titles.add()
    title.title_id = 100001
    title.name = "Demo"
    payload = parsed.SerializeToString()

    payload_path = tmp_path / "0001_title_index_all.pb"
    payload_path.write_bytes(payload)
    metadata = {
        "endpoint": "title_index",
        "identifier": "all",
        "url": "https://jumpg-webapi.tokyo-cdn.com/api/title_list/allV2",
        "params": {"id_length": 6},
        "raw_payload_file": payload_path.name,
        "payload_size_bytes": len(payload),
        "payload_sha256": sha256(payload).hexdigest(),
    }
    (tmp_path / "0001_title_index_all.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = verify_capture_schema(tmp_path)

    assert summary.total_records == 1
    assert summary.endpoint_counts == {"title_index": 1}


def test_verify_capture_schema_against_baseline_with_real_fixture_set() -> None:
    """Verify baseline comparison passes for matching capture and baseline sets."""
    summary = verify_capture_schema_against_baseline(FIXTURE_CAPTURE_DIR, FIXTURE_CAPTURE_DIR)
    assert summary.total_records == 8


def test_verify_capture_schema_against_baseline_detects_drift(tmp_path: Path) -> None:
    """Verify baseline comparison fails when capture signature keys drift."""
    copy_fixture_set(tmp_path)
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
    copy_fixture_set(capture_dir)
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
    copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["endpoint"] = "unsupported_endpoint"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Unsupported endpoint"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_size_mismatch(tmp_path: Path) -> None:
    """Verify verifier catches payload size mismatches from metadata."""
    copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0002_manga_viewer_1000311.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["payload_size_bytes"] = 1
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Payload size mismatch"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_sha_mismatch(tmp_path: Path) -> None:
    """Verify verifier catches payload checksum mismatches from metadata."""
    copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0002_manga_viewer_1000311.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["payload_sha256"] = "0" * 64
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Payload sha256 mismatch"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_manga_viewer_missing_pages(tmp_path: Path) -> None:
    """Verify verifier rejects manga_viewer payloads with empty pages."""
    copy_fixture_set(tmp_path)

    payload_path = tmp_path / "0002_manga_viewer_1000311.pb"
    parsed = Response.FromString(payload_path.read_bytes())
    parsed.success.manga_viewer.ClearField("pages")
    mutated_payload = parsed.SerializeToString()
    payload_path.write_bytes(mutated_payload)

    meta_path = tmp_path / "0002_manga_viewer_1000311.meta.json"
    update_payload_metadata(meta_path, mutated_payload)

    with pytest.raises(CaptureVerificationError, match="No pages found in manga_viewer payload"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_title_detail_missing_chapter_lists(
    tmp_path: Path,
) -> None:
    """Verify verifier rejects title_detail payloads with no grouped or flat chapters."""
    copy_fixture_set(tmp_path)

    payload_path = tmp_path / "0001_title_detailV3_100010.pb"
    parsed = Response.FromString(payload_path.read_bytes())
    parsed.success.title_detail_view.ClearField("chapter_list_group")
    mutated_payload = parsed.SerializeToString()
    payload_path.write_bytes(mutated_payload)

    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    update_payload_metadata(meta_path, mutated_payload)

    with pytest.raises(CaptureVerificationError, match="No chapter_list_group records"):
        verify_capture_schema(tmp_path)


def test_load_metadata_rejects_non_dict_json(tmp_path: Path) -> None:
    """Verify metadata loader requires a JSON object."""
    meta_path = tmp_path / "record.meta.json"
    meta_path.write_text("[]", encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Metadata file is not an object"):
        load_metadata(meta_path)


def test_verify_capture_schema_fails_for_missing_directory() -> None:
    """Verify verifier rejects nonexistent capture directories."""
    with pytest.raises(CaptureVerificationError, match="Capture directory not found"):
        verify_capture_schema("does-not-exist")


def test_verify_capture_schema_fails_for_missing_endpoint(tmp_path: Path) -> None:
    """Verify verifier rejects metadata without endpoint values."""
    copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["endpoint"] = ""
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(CaptureVerificationError, match="Missing endpoint"):
        verify_capture_schema(tmp_path)


def test_verify_capture_schema_fails_for_missing_raw_payload_reference(tmp_path: Path) -> None:
    """Verify verifier rejects metadata pointing to missing raw payload files."""
    copy_fixture_set(tmp_path)
    meta_path = tmp_path / "0001_title_detailV3_100010.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["raw_payload_file"] = "missing.pb"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(
        CaptureVerificationError, match="Missing raw payload file referenced by metadata"
    ):
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
