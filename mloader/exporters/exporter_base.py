from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Union, Optional

from mloader.constants import Language
from mloader.response_pb2 import Title, Chapter # type: ignore
from mloader.utils import escape_path, is_oneshot, is_windows


def _is_extra(chapter_name: str) -> bool:
    """
    Determine if the chapter is marked as extra.
    A chapter is considered extra if its name (after stripping '#' characters)
    equals "ex".
    """
    return chapter_name.strip("#").lower() == "ex"


class ExporterBase(metaclass=ABCMeta):
    """
    Base class for exporting manga chapters to various formats.
    """
    FORMAT_REGISTRY = {}

    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
    ):
        """
        Initialize the exporter with destination, title/chapter metadata, and options.
        """
        self.destination = destination

        # Adjust for Windows extended-length path if needed.
        if is_windows():
            resolved_path = Path(self.destination).resolve().as_posix()
            self.destination = f"\\\\?\\{resolved_path}"

        self.add_chapter_title = add_chapter_title
        self.add_chapter_subdir = add_chapter_subdir

        # Sanitize the manga title.
        self.title_name = escape_path(title.name).title()

        # Store the chapter for later use (for naming).
        self.chapter = chapter
        self.next_chapter = next_chapter

        # Determine oneshot and extra status (if you need these flags elsewhere).
        self.is_oneshot = is_oneshot(chapter.name, chapter.sub_title)
        self.is_extra = _is_extra(chapter.name)

        # Build the chapter filename parts using our custom methods.
        self._chapter_prefix = self._format_chapter_prefix(self.title_name, chapter.name, title.language)
        self._chapter_suffix = self._format_chapter_suffix()
        self.chapter_name = f"{self._chapter_prefix} {self._chapter_suffix}"

    def _format_chapter_prefix(
        self,
        title_name: str,
        chapter_name: str,
        language: int,
        next_chapter_name: Optional[str] = None,
    ) -> str:
        """
        Build the chapter prefix using the manga title and chapter title.
        If the manga language is not English, add a language label.
        """
        safe_chapter_name = escape_path(chapter_name)
        lang = ""
        if Language(language) != Language.ENGLISH:
            lang = f" [{Language(language).name}]"
        return f"{title_name}{lang} - {safe_chapter_name}"

    def _format_chapter_suffix(self) -> str:
        """
        Build the chapter suffix using the chapter subtitle.
        If no subtitle is provided, default to "Unknown".
        """
        safe_subtitle = (
            escape_path(self.chapter.sub_title)
            if self.chapter.sub_title and self.chapter.sub_title.strip()
            else "Unknown"
        )
        return f"- {safe_subtitle}"

    def format_page_name(self, page: Union[int, range], ext: str = ".jpg") -> str:
        """
        Format the filename for an individual manga page.
        """
        if isinstance(page, range):
            page_str = f"p{page.start:0>3}-{page.stop:0>3}"
        else:
            page_str = f"p{page:0>3}"
        ext = ext.lstrip(".")
        return f"{self._chapter_prefix} - {page_str} {self._chapter_suffix}.{ext}"

    def close(self):
        """
        Finalize the export process (to be optionally overridden by concrete exporters).
        """
        pass

    def __init_subclass__(cls, **kwargs) -> None:
        """
        Automatically register subclasses by their format.
        """
        cls.FORMAT_REGISTRY[cls.format] = cls
        return super().__init_subclass__(**kwargs)

    @abstractmethod
    def add_image(self, image_data: bytes, index: Union[int, range]):
        """
        Add an image to the export output.
        """
        pass

    @abstractmethod
    def skip_image(self, index: Union[int, range]) -> bool:
        """
        Determine whether an image should be skipped.
        """
        pass

    @property
    @abstractmethod
    def format(self) -> str:
        """
        The file format of the exporter (e.g., "pdf").
        """
        pass