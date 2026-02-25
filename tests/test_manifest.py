"""Tests for persistent title download manifest behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mloader.manga_loader.manifest import (
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA,
    MANIFEST_VERSION,
    TitleDownloadManifest,
)


def _load_manifest(path: Path) -> dict[str, object]:
    """Read manifest JSON payload from ``path``."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_tracks_started_completed_and_failed_states(tmp_path: Path) -> None:
    """Verify manifest writes state transitions and persists across reloads."""
    manifest = TitleDownloadManifest(tmp_path)
    manifest_path = tmp_path / MANIFEST_FILENAME

    manifest.mark_started(1, chapter_name="#1", sub_title="Start", output_format="pdf")
    payload_started = _load_manifest(manifest_path)
    chapter_started = payload_started["chapters"]["1"]
    assert chapter_started["status"] == "in_progress"
    assert chapter_started["output_format"] == "pdf"

    manifest.mark_completed(1, output_path="/tmp/out.pdf")
    manifest_reloaded = TitleDownloadManifest(tmp_path)
    payload_completed = _load_manifest(manifest_path)
    chapter_completed = payload_completed["chapters"]["1"]
    assert chapter_completed["status"] == "completed"
    assert chapter_completed["output_path"] == "/tmp/out.pdf"
    assert manifest_reloaded.is_completed(1) is True

    manifest_reloaded.mark_failed(2, error="boom")
    payload_failed = _load_manifest(manifest_path)
    chapter_failed = payload_failed["chapters"]["2"]
    assert chapter_failed["status"] == "failed"
    assert chapter_failed["error"] == "boom"


def test_manifest_load_migrates_v1_payload_and_persists_current_schema(tmp_path: Path) -> None:
    """Verify versioned legacy payloads are migrated to latest schema on load."""
    manifest_path = tmp_path / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "chapters": {
                    "3": {
                        "chapter_id": 3,
                        "status": "completed",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = TitleDownloadManifest(tmp_path)

    assert manifest.is_completed(3) is True
    migrated_payload = _load_manifest(manifest_path)
    assert migrated_payload["version"] == MANIFEST_VERSION
    assert migrated_payload["schema"] == MANIFEST_SCHEMA


def test_manifest_load_migrates_unversioned_payload_shape(tmp_path: Path) -> None:
    """Verify old unversioned chapter-map payloads are migrated and preserved."""
    manifest_path = tmp_path / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(
            {
                "7": {
                    "chapter_id": 7,
                    "status": "completed",
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = TitleDownloadManifest(tmp_path)

    assert manifest.is_completed(7) is True
    migrated_payload = _load_manifest(manifest_path)
    assert migrated_payload["version"] == MANIFEST_VERSION
    assert migrated_payload["schema"] == MANIFEST_SCHEMA
    assert migrated_payload["chapters"]["7"]["status"] == "completed"


def test_manifest_load_accepts_future_version_without_migration(tmp_path: Path) -> None:
    """Verify newer unknown manifest versions still load chapter completion state."""
    manifest_path = tmp_path / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION + 1,
                "chapters": {
                    "9": {
                        "chapter_id": 9,
                        "status": "completed",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = TitleDownloadManifest(tmp_path)

    assert manifest.is_completed(9) is True


def test_manifest_load_returns_empty_when_migration_step_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify missing migration mapping fails closed with empty in-memory chapter state."""
    manifest_path = tmp_path / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(
            {
                "version": 0,
                "chapters": {
                    "1": {
                        "chapter_id": 1,
                        "status": "completed",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("mloader.manga_loader.manifest.MANIFEST_MIGRATIONS", {})

    manifest = TitleDownloadManifest(tmp_path)

    assert manifest.is_completed(1) is False


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        "[]",
        "{}",
        '{"chapters": []}',
    ],
)
def test_manifest_load_handles_invalid_or_unexpected_payloads(
    tmp_path: Path,
    content: str,
) -> None:
    """Verify malformed manifest payloads are ignored without raising."""
    manifest_path = tmp_path / MANIFEST_FILENAME
    manifest_path.write_text(content, encoding="utf-8")

    manifest = TitleDownloadManifest(tmp_path)

    assert manifest.is_completed(1) is False

    manifest.mark_started(1, chapter_name="#1", sub_title="Sub", output_format="cbz")
    payload = _load_manifest(manifest_path)
    assert payload["chapters"]["1"]["status"] == "in_progress"


def test_manifest_autosave_disabled_requires_flush(tmp_path: Path) -> None:
    """Verify autosave-disabled manifests persist changes only on explicit flush."""
    manifest = TitleDownloadManifest(tmp_path, autosave=False)
    manifest_path = tmp_path / MANIFEST_FILENAME

    manifest.mark_started(1, chapter_name="#1", sub_title="Sub", output_format="cbz")
    assert manifest_path.exists() is False

    manifest.mark_completed(1, output_path="/tmp/out.cbz")
    assert manifest_path.exists() is False

    manifest.flush()
    payload = _load_manifest(manifest_path)
    assert payload["chapters"]["1"]["status"] == "completed"
    assert payload["chapters"]["1"]["output_path"] == "/tmp/out.cbz"


def test_manifest_reset_clears_manifest_file(tmp_path: Path) -> None:
    """Verify reset removes persisted manifest state."""
    manifest = TitleDownloadManifest(tmp_path)
    manifest_path = tmp_path / MANIFEST_FILENAME
    manifest.mark_completed(1)
    assert manifest_path.exists() is True

    manifest.reset()

    assert manifest_path.exists() is False
    assert manifest.is_completed(1) is False


def test_manifest_autosave_merges_updates_across_instances(tmp_path: Path) -> None:
    """Verify separate instances can append chapter state without dropping previous entries."""
    manifest_a = TitleDownloadManifest(tmp_path)
    manifest_b = TitleDownloadManifest(tmp_path)

    manifest_a.mark_completed(1, output_path="/tmp/one.cbz")
    manifest_b.mark_failed(2, error="boom")

    payload = _load_manifest(tmp_path / MANIFEST_FILENAME)
    assert set(payload["chapters"].keys()) == {"1", "2"}


def test_manifest_save_persists_pending_changes(tmp_path: Path) -> None:
    """Verify explicit save persists in-memory changes for autosave-disabled mode."""
    manifest = TitleDownloadManifest(tmp_path, autosave=False)
    manifest.mark_failed(7, error="boom")

    manifest.save()

    payload = _load_manifest(tmp_path / MANIFEST_FILENAME)
    assert payload["chapters"]["7"]["status"] == "failed"


def test_manifest_flush_returns_when_dirty_clears_during_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify flush exits when dirty state is cleared before locked write branch."""
    manifest = TitleDownloadManifest(tmp_path, autosave=False)
    manifest._dirty = True

    class Lock:
        def __enter__(self) -> None:
            manifest._dirty = False
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(manifest, "_lock", Lock())
    manifest.flush()
    assert manifest._dirty is False


def test_manifest_mark_entry_noops_when_update_is_identical_autosave_true(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify autosave mode skips writes when chapter entry does not change."""
    monkeypatch.setattr("mloader.manga_loader.manifest._utc_timestamp", lambda: "2026-02-24T00:00:00Z")
    manifest = TitleDownloadManifest(tmp_path)
    manifest.mark_failed(1, error="boom")
    payload_before = _load_manifest(tmp_path / MANIFEST_FILENAME)

    manifest.mark_failed(1, error="boom")

    payload_after = _load_manifest(tmp_path / MANIFEST_FILENAME)
    assert payload_before == payload_after


def test_manifest_mark_entry_noops_when_update_is_identical_autosave_false(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify autosave-disabled mode skips dirtying when chapter entry is unchanged."""
    monkeypatch.setattr("mloader.manga_loader.manifest._utc_timestamp", lambda: "2026-02-24T00:00:00Z")
    manifest = TitleDownloadManifest(tmp_path, autosave=False)
    manifest.mark_failed(2, error="boom")
    manifest._dirty = False

    manifest.mark_failed(2, error="boom")

    assert manifest._dirty is False


def test_manifest_reset_is_noop_when_file_is_missing(tmp_path: Path) -> None:
    """Verify reset does not fail when manifest file does not exist."""
    manifest = TitleDownloadManifest(tmp_path)

    manifest.reset()

    assert (tmp_path / MANIFEST_FILENAME).exists() is False
