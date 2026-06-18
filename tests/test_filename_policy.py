"""Tests for centralized downloader filename policy."""

from __future__ import annotations

from mloader.manga_loader.filename_policy import FilenamePolicy
from tests.downloader_helpers import chapter as _chapter


def test_filename_policy_preserves_title_directory_contract() -> None:
    """Verify title directory naming keeps the existing title-case sanitized contract."""
    assert FilenamePolicy.title_directory_name("dr. STONE") == "Dr Stone"


def test_filename_policy_preserves_chapter_stem_contract() -> None:
    """Verify chapter filename stems match existing golden naming behavior."""
    assert (
        FilenamePolicy.build_expected_filename(
            "Dr Stone",
            _chapter(1000311, "#002"),
            "Z=2 Fantasy vs. Science?",
        )
        == "Dr Stone - 002 - Z 2 Fantasy vs Science"
    )


def test_build_expected_filename_legacy_style_without_language_tag() -> None:
    """Verify legacy mode keeps the old filename stem shape with no language tag."""
    assert (
        FilenamePolicy.build_expected_filename(
            "Dr Stone",
            _chapter(1000311, "#002"),
            "Z=2 Fantasy vs. Science?",
            8,
            filename_style="legacy",
        )
        == "Dr Stone - 002 - Z 2 Fantasy vs Science"
    )


def test_build_expected_filename_new_style_appends_language_tag() -> None:
    """Verify new mode appends the language tag in title-level chapter filenames."""
    assert (
        FilenamePolicy.build_expected_filename(
            "Dr Stone",
            _chapter(1000311, "#002"),
            "Z=2 Fantasy vs. Science?",
            8,
            filename_style="new",
        )
        == "Dr Stone [VIETNAMESE] - 002 - Z 2 Fantasy vs Science"
    )
