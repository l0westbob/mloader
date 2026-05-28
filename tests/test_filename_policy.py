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
