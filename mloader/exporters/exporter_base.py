"""Base exporter contract and shared naming logic."""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import ClassVar, Optional, Union

from mloader.constants import Language
from mloader.response_pb2 import Chapter, Title  # type: ignore
from mloader.utils import escape_path, is_oneshot, is_windows


def _is_extra(chapter_name: str) -> bool:
    """Return ``True`` when a chapter name represents an extra chapter."""
    return chapter_name.strip("#").lower() == "ex"


def _format_language_tag(language: int) -> str:
    """Build a stable language tag for chapter names, including unknown codes."""
    if language == 8:  # Legacy Vietnamese code observed in older payloads.
        return " [VIETNAMESE]"

    try:
        parsed_language = Language(language)
    except ValueError:
        return f" [LANG-{language}]"

    if parsed_language == Language.ENGLISH:
        return ""

    return f" [{parsed_language.name}]"


class ExporterBase(metaclass=ABCMeta):
    """Define the interface and shared behavior for all exporters."""

    FORMAT_REGISTRY: dict[str, type["ExporterBase"]] = {}
    format: ClassVar[str]

    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
    ) -> None:
        """Initialize exporter state and derive chapter naming parts."""
        self.destination = destination

        if is_windows():
            resolved_path = Path(self.destination).resolve().as_posix()
            self.destination = f"\\\\?\\{resolved_path}"

        self.add_chapter_title = add_chapter_title
        self.add_chapter_subdir = add_chapter_subdir
        self.title_name = escape_path(title.name).title()
        self.chapter = chapter
        self.next_chapter = next_chapter
        self.is_oneshot = is_oneshot(chapter.name, chapter.sub_title)
        self.is_extra = _is_extra(chapter.name)

        self._chapter_prefix = self._format_chapter_prefix(
            self.title_name,
            chapter.name,
            title.language,
        )
        self._chapter_suffix = self._format_chapter_suffix()
        self.chapter_name = f"{self._chapter_prefix} {self._chapter_suffix}"

    def _format_chapter_prefix(
        self,
        title_name: str,
        chapter_name: str,
        language: int,
        next_chapter_name: Optional[str] = None,
    ) -> str:
        """Build the filename prefix used by chapter and page outputs."""
        _ = next_chapter_name
        safe_chapter_name = escape_path(chapter_name)
        lang = _format_language_tag(language)
        return f"{title_name}{lang} - {safe_chapter_name}"

    def _format_chapter_suffix(self) -> str:
        """Build the filename suffix based on chapter subtitle."""
        safe_subtitle = (
            escape_path(self.chapter.sub_title)
            if self.chapter.sub_title and self.chapter.sub_title.strip()
            else "Unknown"
        )
        return f"- {safe_subtitle}"

    def format_page_name(self, page: Union[int, range], ext: str = ".jpg") -> str:
        """Return the canonical page filename for ``page``."""
        if isinstance(page, range):
            page_str = f"p{page.start:0>3}-{page.stop:0>3}"
        else:
            page_str = f"p{page:0>3}"
        return f"{self._chapter_prefix} - {page_str} {self._chapter_suffix}.{ext.lstrip('.')}"

    def close(self) -> None:
        """Finalize exporter resources if needed."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Register subclasses by their declared ``format`` key."""
        format_name = getattr(cls, "format", "")
        if not isinstance(format_name, str) or not format_name:
            raise TypeError("Exporter subclasses must define a non-empty string 'format'.")
        cls.FORMAT_REGISTRY[format_name] = cls
        super().__init_subclass__(**kwargs)

    @abstractmethod
    def add_image(self, image_data: bytes, index: Union[int, range]) -> None:
        """Persist a single page image."""

    @abstractmethod
    def skip_image(self, index: Union[int, range]) -> bool:
        """Return whether writing ``index`` can be skipped."""
