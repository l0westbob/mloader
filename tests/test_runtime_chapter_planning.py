"""Tests for runtime chapter planning and filename decisions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mloader.domain.planning import title_detail_with_selected_chapters
from mloader.manga_loader.chapter_planning import ChapterMetadata, ChapterPlanner, DownloadPlanner
from mloader.manga_loader.filename_policy import FilenamePolicy
from tests.downloader_helpers import (
    chapter as _chapter,
    title_detail as _title_detail,
)


def test_filter_chapters_to_download_skips_existing_files() -> None:
    """Verify existing chapter files are skipped from download candidates."""
    chapter_data = {
        1024959: ChapterMetadata(
            thumbnail_url="",
            chapter_id=1024959,
            sub_title="Chapter One",
        ),
        102278: ChapterMetadata(
            thumbnail_url="",
            chapter_id=102278,
            sub_title="Chapter Two",
        ),
    }
    chapter1 = _chapter(1024959, "#1024959")
    chapter2 = _chapter(102278, "#102278")
    title_detail = _title_detail(chapters=[chapter1, chapter2])

    existing = [ChapterPlanner.build_expected_filename("My Manga", chapter1, "Chapter One")]

    result = DownloadPlanner.filter_chapters_to_download(
        chapter_data,
        title_detail,
        existing_files=existing,
        requested_chapter_ids={1024959, 102278},
    )

    assert result == [102278]


def test_chapter_output_extension_delegates_to_download_planner() -> None:
    """Verify chapter-level extensions are derived by output format."""
    assert DownloadPlanner.chapter_output_extension("raw") is None
    assert DownloadPlanner.chapter_output_extension("pdf") == "pdf"


def test_extract_chapter_data_from_all_groups() -> None:
    """Verify chapter metadata extraction includes first/mid/last chapter groups."""
    title_detail = _title_detail(
        chapters=[
            _chapter(1024959, "#1", "A", thumbnail_url="t1"),
            _chapter(102278, "#2", "B", thumbnail_url="t2"),
            _chapter(102279, "#3", "C", thumbnail_url="t3"),
        ]
    )

    result = ChapterPlanner.extract_chapter_data(title_detail, FilenamePolicy.prepare_filename)

    assert result[1024959].chapter_id == 1024959
    assert result[102278].chapter_id == 102278
    assert result[102279].chapter_id == 102279
    assert result[102278].sub_title == "B"


def test_extract_chapter_data_keeps_duplicate_subtitles_by_chapter_id() -> None:
    """Verify duplicate subtitles do not overwrite chapter metadata entries."""
    title_detail = _title_detail(
        chapters=[
            _chapter(1024959, "#1", "Same", thumbnail_url="t1"),
            _chapter(102278, "#2", "Same", thumbnail_url="t2"),
        ]
    )

    result = ChapterPlanner.extract_chapter_data(title_detail, FilenamePolicy.prepare_filename)

    assert set(result.keys()) == {1024959, 102278}
    assert result[1024959].sub_title == "Same"
    assert result[102278].sub_title == "Same"


def test_get_existing_files_returns_stems(tmp_path: Path) -> None:
    """Verify existing-file lookup returns PDF stems only."""
    export_path = tmp_path / "manga"
    export_path.mkdir()
    (export_path / "a.pdf").write_bytes(b"1")
    (export_path / "b.pdf").write_bytes(b"2")
    (export_path / "c.cbz").write_bytes(b"3")

    assert sorted(DownloadPlanner.get_existing_files(export_path, output_format="pdf")) == [
        "a",
        "b",
    ]


def test_get_existing_files_returns_empty_when_missing(tmp_path: Path) -> None:
    """Verify existing-file lookup returns empty list for missing export path."""
    assert DownloadPlanner.get_existing_files(tmp_path / "missing", output_format="pdf") == []


def test_get_existing_files_uses_cbz_extension(tmp_path: Path) -> None:
    """Verify existing chapter lookup uses cbz extension in CBZ mode."""
    export_path = tmp_path / "manga"
    export_path.mkdir()
    (export_path / "a.cbz").write_bytes(b"1")
    (export_path / "b.pdf").write_bytes(b"2")

    assert DownloadPlanner.get_existing_files(export_path, output_format="cbz") == ["a"]


def test_get_existing_files_is_disabled_for_raw_mode(tmp_path: Path) -> None:
    """Verify raw mode disables chapter-level existing-file prefiltering."""
    export_path = tmp_path / "manga"
    export_path.mkdir()
    (export_path / "a.pdf").write_bytes(b"1")

    assert DownloadPlanner.get_existing_files(export_path, output_format="raw") == []


def test_filter_chapters_warns_when_chapter_missing(caplog: Any) -> None:
    """Verify missing chapter IDs log a warning and are excluded."""
    chapter_data = {99: ChapterMetadata(thumbnail_url="", chapter_id=99, sub_title="Missing")}
    title_detail = _title_detail(chapters=[])

    with caplog.at_level("WARNING"):
        result = DownloadPlanner.filter_chapters_to_download(
            chapter_data,
            title_detail,
            existing_files=[],
            requested_chapter_ids={102399},
        )

    assert result == []
    assert "not found in title dump" in caplog.text


def test_filter_chapters_accepts_metadata_values() -> None:
    """Verify chapter filtering accepts canonical ``ChapterMetadata`` objects."""
    chapter = _chapter(102305, "#102305")
    title_detail = _title_detail(chapters=[chapter])
    chapter_data = {102305: ChapterMetadata(thumbnail_url="t5", chapter_id=102305, sub_title="Sub")}

    result = DownloadPlanner.filter_chapters_to_download(
        chapter_data,
        title_detail,
        existing_files=[],
        requested_chapter_ids={102305},
    )

    assert result == [102305]


def test_find_chapter_by_id_returns_match_and_none() -> None:
    """Verify chapter lookup returns chapter object when found, else None."""
    chapter = _chapter(1024959, "#1024959")
    title_detail = _title_detail(chapters=[chapter])

    assert ChapterPlanner.find_chapter_by_id(title_detail, 1024959) is chapter
    assert ChapterPlanner.find_chapter_by_id(title_detail, 102278) is None


def test_title_detail_with_selected_chapters_adds_direct_fallback_chapter() -> None:
    """Verify direct-ID fallback chapters are available to downstream filtering."""
    existing = _chapter(1, "#1")
    fallback = _chapter(2, "#2")
    title_detail = _title_detail(chapters=[existing])

    augmented = title_detail_with_selected_chapters(title_detail, [existing, fallback])

    assert augmented is not title_detail
    assert augmented.find_chapter(1) is existing
    assert augmented.find_chapter(2) is fallback


def test_prepare_filename_keeps_text_when_mojibake_fix_fails() -> None:
    """Verify filename sanitizer still returns safe text on decode failures."""
    assert FilenamePolicy.prepare_filename("A\u20ac!") == "A"
