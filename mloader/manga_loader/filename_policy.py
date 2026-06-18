"""Filesystem naming policy for title and chapter outputs."""

from __future__ import annotations

import logging

from mloader.domain.requests import FilenameStyle
from mloader.types import ChapterLike
from mloader.utils import escape_path
from mloader.constants import Language

log = logging.getLogger(__name__)


def _format_language_tag(language: int) -> str:
    """Build a stable language tag for chapter names."""
    if language == 8:  # Legacy Vietnamese code observed in older payloads.
        return " [VIETNAMESE]"

    try:
        parsed_language = Language(language)
    except ValueError:
        return f" [LANG-{language}]"

    if parsed_language == Language.ENGLISH:
        return ""

    return f" [{parsed_language.name}]"


class FilenamePolicy:
    """Centralize filename normalization for downloader outputs."""

    @staticmethod
    def format_language_tag(language: int) -> str:
        """Build a stable language tag for chapter names."""
        return _format_language_tag(language)

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
        title_language: int = 0,
        *,
        filename_style: FilenameStyle = "legacy",
    ) -> str:
        """Build normalized filename stem expected for chapter-level outputs."""
        _ = title_language
        _ = filename_style
        sanitized_title = FilenamePolicy.prepare_filename(title_name)
        sanitized_chapter_name = FilenamePolicy.prepare_filename(
            chapter_obj.name.lstrip("#").strip()
        )
        sanitized_sub_title = FilenamePolicy.prepare_filename(sub_title)

        chapter_prefix = (
            f"{sanitized_title}{_format_language_tag(title_language)} - {sanitized_chapter_name}"
            if filename_style == "new"
            else f"{sanitized_title} - {sanitized_chapter_name}"
        )
        return f"{chapter_prefix} - {sanitized_sub_title}"
