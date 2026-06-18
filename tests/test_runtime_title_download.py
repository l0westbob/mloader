"""Tests for title-level download orchestration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from mloader.manga_loader.chapter_planning import ChapterMetadata
from mloader.manga_loader.filename_policy import FilenamePolicy
from mloader.manga_loader import title_download as title_download_module
from mloader.manga_loader.manifest_tracking import ManifestTracker
from tests.downloader_helpers import (
    dummy_downloader,
    full_downloader,
    chapter as _chapter,
    run_report as _run_report,
    title_detail as _title_detail,
    title_plan as _title_plan,
)


class FakeManifestBase:
    """Manifest double implementing the title-download manifest protocol."""

    def __init__(self, _export_path: Path | None = None, *, autosave: bool = False) -> None:
        """Accept manifest constructor arguments used by the runtime factory."""
        del _export_path, autosave

    def reset(self) -> None:
        """No-op reset."""

    def flush(self) -> None:
        """No-op flush."""

    def is_completed(self, chapter_id: int) -> bool:
        """Treat every chapter as incomplete by default."""
        del chapter_id
        return False

    def mark_started(
        self,
        chapter_id: int,
        *,
        chapter_name: str,
        sub_title: str,
        output_format: str,
    ) -> None:
        """No-op start marker."""
        del chapter_id, chapter_name, sub_title, output_format

    def mark_completed(self, chapter_id: int, *, output_path: str | None = None) -> None:
        """No-op completion marker."""
        del chapter_id, output_path

    def mark_failed(self, chapter_id: int, *, error: str) -> None:
        """No-op failure marker."""
        del chapter_id, error


def test_manifest_tracker_mark_failed_noops_without_active_manifest() -> None:
    """Verify manifest failure tracking is disabled unless resumable state is active."""
    manifest = FakeManifestBase()

    ManifestTracker.mark_failed(manifest, resume=False, chapter_id=1, error="boom")
    ManifestTracker.mark_failed(None, resume=True, chapter_id=1, error="boom")


def test_process_title_with_no_chapters_to_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _process_title returns early when no chapters remain."""
    downloader = full_downloader()
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])

    downloader._process_title(1, 1, _title_plan(title_id=10, chapter_ids={1}), report=_run_report())


def test_process_title_clears_title_cache_after_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify title-level cache clear hook runs after title processing."""
    downloader = full_downloader()
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])
    clear_calls: list[tuple[int, set[int]]] = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        downloader,
        "_clear_api_caches_for_title",
        lambda title_id, chapter_ids: clear_calls.append((title_id, set(chapter_ids))),
    )

    downloader._process_title(
        1,
        1,
        _title_plan(title_id=10, chapter_ids={1, 2}),
        report=_run_report(),
    )

    assert clear_calls == [(10, {1, 2})]


def test_process_title_downloads_sorted_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _process_title processes candidate chapters in sorted order."""
    downloader = full_downloader()
    title_dump = _title_detail(chapters=[_chapter(3, "#3", "sub")])
    processed: list[tuple[int, int, int]] = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(
        downloader,
        "_extract_chapter_data",
        lambda _dump: {3: ChapterMetadata(thumbnail_url="", chapter_id=3, sub_title="sub")},
        raising=False,
    )
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(
        downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [5, 2, 3]
    )
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda title, index, total, chapter_id, **kwargs: processed.append(
            (index, total, chapter_id)
        ),
    )

    downloader._process_title(
        1,
        1,
        _title_plan(title_id=10, chapter_ids={2, 3, 5}),
        report=_run_report(),
    )

    assert processed == [(1, 3, 2), (2, 3, 3), (3, 3, 5)]


def test_process_title_dumps_metadata_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify metadata export is invoked when loader meta flag is enabled."""
    downloader = full_downloader(meta=True)
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])
    calls = {"metadata": 0}

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        downloader,
        "_dump_title_metadata",
        lambda *_args, **_kwargs: calls.__setitem__("metadata", calls["metadata"] + 1),
    )

    downloader._process_title(1, 1, _title_plan(title_id=10, chapter_ids={1}), report=_run_report())

    assert calls["metadata"] == 1


def test_process_title_dumps_cover_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cover export is invoked when loader cover flag is enabled."""
    downloader = dummy_downloader(cover=True)
    title_detail = _title_detail(name="Title", author="Author", chapters=[])
    calls = {"cover": 0}

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_detail, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(
        downloader,
        "_dump_title_cover",
        lambda *_args, **_kwargs: calls.__setitem__("cover", calls["cover"] + 1),
        raising=False,
    )
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])

    downloader._process_title(1, 1, _title_plan(title_id=10, chapter_ids={1}), report=_run_report())

    assert calls["cover"] == 1


def test_process_title_cover_export_failure_logs_warning_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify cover export failures do not abort title processing."""
    downloader = dummy_downloader(cover=True)
    title_detail = _title_detail(name="Title", author="Author", chapters=[])

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_detail, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(
        downloader,
        "_dump_title_cover",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("cover failed")),
        raising=False,
    )
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])

    downloader._process_title(1, 1, _title_plan(title_id=10, chapter_ids={1}), report=_run_report())

    assert "Cover export failed" in caplog.text


def test_process_title_skips_manifest_completed_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify title processing excludes chapter IDs marked completed in manifest."""
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])
    processed: list[int] = []

    class FakeManifest(FakeManifestBase):
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            """Store nothing; behavior is fully deterministic for the test."""
            del autosave

        def is_completed(self, chapter_id: int) -> bool:
            """Mark chapter 2 as already completed."""
            return chapter_id == 2

        def flush(self) -> None:
            """No-op flush for downloader finalize hooks."""

    downloader = full_downloader(manifest_factory=FakeManifest)
    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(
        downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2, 3]
    )
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda _title, _index, _total, chapter_id, **kwargs: processed.append(chapter_id),
    )

    report = _run_report()
    downloader._process_title(
        1,
        1,
        _title_plan(title_id=10, chapter_ids={1, 2, 3}),
        report=report,
    )

    assert processed == [1, 3]
    assert report.skipped_manifest == 1


def test_process_title_records_failed_chapter_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify per-chapter failures are collected and run continues."""
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])
    processed: list[int] = []
    marked_failed: list[int] = []
    flush_calls = 0

    class FakeManifest(FakeManifestBase):
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            del autosave

        def is_completed(self, chapter_id: int) -> bool:
            del chapter_id
            return False

        def mark_failed(self, chapter_id: int, *, error: str) -> None:
            del error
            marked_failed.append(chapter_id)

        def flush(self) -> None:
            nonlocal flush_calls
            flush_calls += 1

    def _process_chapter(
        _title: Any,
        _index: int,
        _total: int,
        chapter_id: int,
        **kwargs: Any,
    ) -> None:
        del kwargs
        if chapter_id == 2:
            raise RuntimeError("boom")
        processed.append(chapter_id)

    downloader = full_downloader(manifest_factory=FakeManifest)
    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(
        downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2, 3]
    )
    monkeypatch.setattr(downloader, "_process_chapter", _process_chapter)

    report = _run_report()
    downloader._process_title(
        1,
        1,
        _title_plan(title_id=10, chapter_ids={1, 2, 3}),
        report=report,
    )

    assert processed == [1, 3]
    assert report.downloaded == 2
    assert report.failed == 1
    assert report.failed_chapter_ids == [2]
    assert marked_failed == [2]
    assert flush_calls >= 2


def test_process_title_renames_legacy_files_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify existing legacy chapter files are renamed before filtering."""
    title_id = 10
    chapter_id = 1
    chapter = _chapter(chapter_id, "#1", "Sub")
    title_dump = _title_detail(
        title_id=title_id,
        name="My Manga",
        chapters=[chapter],
    )
    title_dump = replace(title_dump, title=replace(title_dump.title, language=8))
    title_name = FilenamePolicy.title_directory_name("My Manga")
    legacy_file = FilenamePolicy.build_expected_filename(
        title_name,
        chapter,
        "Sub",
        8,
        filename_style="legacy",
    )
    expected_file = FilenamePolicy.build_expected_filename(
        title_name,
        chapter,
        "Sub",
        8,
        filename_style="new",
    )
    export_path = tmp_path / title_name
    export_path.mkdir(parents=True)
    (export_path / f"{legacy_file}.pdf").write_text("already-downloaded")

    downloader = full_downloader(destination=str(tmp_path))
    downloader.context = replace(
        downloader.context,
        filename_style="new",
        rename_existing_filenames=True,
    )
    processed: list[int] = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(
        downloader,
        "_extract_chapter_data",
        lambda _dump: {chapter_id: ChapterMetadata("", chapter_id, "Sub")},
        raising=False,
    )
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda *args, **kwargs: processed.append(chapter_id),
    )

    title_plan = _title_plan(title_id=title_id, chapter_ids={chapter_id})
    title_plan = replace(title_plan, title_detail=title_dump)

    downloader._process_title(
        1,
        1,
        title_plan,
        report=_run_report(),
    )

    assert processed == []
    assert not (export_path / f"{legacy_file}.pdf").exists()
    assert (export_path / f"{expected_file}.pdf").exists()


def test_rename_existing_filenames_skips_unsupported_output_format() -> None:
    """Verify filename migration is skipped for image output formats."""
    title_detail = _title_detail(name="My Manga", chapters=[_chapter(1, "#1")])
    title_name = FilenamePolicy.title_directory_name("My Manga")
    expected_file = FilenamePolicy.build_expected_filename(
        title_name,
        _chapter(1, "#1"),
        "Sub",
        0,
        filename_style="new",
    )

    export_path = Path("/tmp") / title_name
    export_path.mkdir(exist_ok=True)
    title_download_module._rename_existing_filenames_to_style(
        output_format="raw",
        export_path=export_path,
        title_detail=title_detail,
        chapter_data={1: ChapterMetadata("", 1, "Sub")},
        filename_style="new",
    )

    assert not (export_path / f"{expected_file}.raw").exists()


def test_rename_existing_filenames_handles_missing_chapter_data() -> None:
    """Verify migration ignores stale metadata entries with missing chapter IDs."""
    title_detail = _title_detail(name="My Manga", chapters=[])
    export_path = Path("/tmp") / "My Manga"
    export_path.mkdir(exist_ok=True)
    original_files = set(export_path.glob("*"))

    title_download_module._rename_existing_filenames_to_style(
        output_format="pdf",
        export_path=export_path,
        title_detail=title_detail,
        chapter_data={1: ChapterMetadata("", 1, "Sub")},
        filename_style="new",
    )

    assert set(export_path.glob("*")) == original_files


def test_rename_existing_filenames_skips_when_style_is_unchanged() -> None:
    """Verify migration skips entries when the legacy and target filename styles are equal."""
    title = _title_detail(name="My Manga", chapters=[_chapter(1, "#1", "")])
    title = replace(title, title=replace(title.title, language=8))
    title_name = FilenamePolicy.title_directory_name("My Manga")
    legacy_file = FilenamePolicy.build_expected_filename(
        title_name,
        _chapter(1, "#1", ""),
        "",
        8,
        filename_style="legacy",
    )

    export_path = Path("/tmp") / title_name
    export_path.mkdir(exist_ok=True)
    expected_path = export_path / f"{legacy_file}.pdf"
    expected_path.write_text("already-downloaded")

    title_download_module._rename_existing_filenames_to_style(
        output_format="pdf",
        export_path=export_path,
        title_detail=title,
        chapter_data={1: ChapterMetadata("", 1, "")},
        filename_style="legacy",
    )

    assert expected_path.exists()


def test_process_title_on_keyboard_interrupt_marks_manifest_and_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify interrupt during chapter processing marks failure, flushes, and re-raises."""
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])
    marked_failed: list[int] = []
    flush_calls = 0

    class FakeManifest(FakeManifestBase):
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            del autosave

        def is_completed(self, chapter_id: int) -> bool:
            del chapter_id
            return False

        def mark_failed(self, chapter_id: int, *, error: str) -> None:
            del error
            marked_failed.append(chapter_id)

        def flush(self) -> None:
            nonlocal flush_calls
            flush_calls += 1

    downloader = full_downloader(manifest_factory=FakeManifest)
    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1])
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    report = _run_report()
    with pytest.raises(KeyboardInterrupt):
        downloader._process_title(1, 1, _title_plan(title_id=10, chapter_ids={1}), report=report)

    assert report.failed == 1
    assert report.failed_chapter_ids == [1]
    assert marked_failed == [1]
    assert flush_calls >= 2


def test_process_title_resume_skips_completed_and_retries_failed_after_restart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify manifest resume across two runs skips completed and retries failed chapters."""
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])

    first_run = full_downloader(destination=str(tmp_path))
    first_attempts: list[int] = []

    def _first_process_chapter(
        _title: Any,
        _index: int,
        _total: int,
        chapter_id: int,
        **kwargs: Any,
    ) -> None:
        manifest = kwargs.get("manifest")
        first_attempts.append(chapter_id)
        if chapter_id == 2:
            raise RuntimeError("boom")
        if manifest is not None:
            manifest.mark_completed(chapter_id)

    monkeypatch.setattr(first_run, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(first_run, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(first_run, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(first_run, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2])
    monkeypatch.setattr(first_run, "_process_chapter", _first_process_chapter)

    first_report = _run_report()
    first_run._process_title(
        1,
        1,
        _title_plan(title_id=10, chapter_ids={1, 2}),
        report=first_report,
    )

    assert first_attempts == [1, 2]
    assert first_report.downloaded == 1
    assert first_report.failed == 1
    assert first_report.failed_chapter_ids == [2]

    second_run = full_downloader(destination=str(tmp_path))
    second_attempts: list[int] = []

    monkeypatch.setattr(second_run, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(second_run, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(second_run, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(second_run, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2])
    monkeypatch.setattr(
        second_run,
        "_process_chapter",
        lambda _title, _index, _total, chapter_id, **kwargs: second_attempts.append(chapter_id),
    )

    second_report = _run_report()
    second_run._process_title(
        1,
        1,
        _title_plan(title_id=10, chapter_ids={1, 2}),
        report=second_report,
    )

    assert second_attempts == [2]
    assert second_report.downloaded == 1
    assert second_report.skipped_manifest == 1
    assert second_report.failed == 0


def test_process_title_disables_manifest_when_resume_is_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --no-resume mode skips manifest-based chapter filtering."""
    downloader = full_downloader(resume=False)
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])
    processed: list[int] = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2])
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda _title, _index, _total, chapter_id, **kwargs: processed.append(chapter_id),
    )

    report = _run_report()
    downloader._process_title(
        1,
        1,
        _title_plan(title_id=10, chapter_ids={1, 2}),
        report=report,
    )

    assert processed == [1, 2]
    assert report.skipped_manifest == 0


def test_process_title_resets_manifest_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --manifest-reset clears existing per-title manifest state."""
    title_dump = _title_detail(name="My Manga", author="A", chapters=[])
    reset_calls = 0

    class FakeManifest(FakeManifestBase):
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            del autosave

        def reset(self) -> None:
            nonlocal reset_calls
            reset_calls += 1

        def is_completed(self, chapter_id: int) -> bool:
            del chapter_id
            return False

        def flush(self) -> None:
            """No-op flush for downloader finalize hooks."""

    downloader = full_downloader(manifest_reset=True, manifest_factory=FakeManifest)
    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])
    downloader._process_title(1, 1, _title_plan(title_id=10, chapter_ids={1}), report=_run_report())

    assert reset_calls == 1
