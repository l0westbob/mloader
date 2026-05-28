"""Filesystem naming policy for title and chapter outputs."""

from __future__ import annotations

import logging

from mloader.types import ChapterLike
from mloader.utils import escape_path

log = logging.getLogger(__name__)


class FilenamePolicy:
    """Centralize filename normalization for downloader outputs."""

    @staticmethod
    def prepare_filename(text: str) -> str:
        """Fix common encoding glitches and sanitize text for filesystem use."""
        fixed_text = text
        try:
            fixed_text = text.encode("latin1").decode("utf8")
        except UnicodeEncodeError, UnicodeDecodeError:
            log.warning(f"    Encoding fix skipped for: {text}")
        return escape_path(fixed_text)

    @staticmethod
    def title_directory_name(title_name: str) -> str:
        """Return the title directory name used for all per-title outputs."""
        return FilenamePolicy.prepare_filename(title_name).title()

    @staticmethod
    def build_expected_filename(
        title_name: str,
        chapter_obj: ChapterLike,
        sub_title: str,
    ) -> str:
        """Build normalized filename stem expected for chapter-level outputs."""
        sanitized_title = FilenamePolicy.prepare_filename(title_name)
        sanitized_chapter_name = FilenamePolicy.prepare_filename(
            chapter_obj.name.lstrip("#").strip()
        )
        sanitized_sub_title = FilenamePolicy.prepare_filename(sub_title)
        return f"{sanitized_title} - {sanitized_chapter_name} - {sanitized_sub_title}"
