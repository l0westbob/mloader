from abc import ABCMeta, abstractmethod
from itertools import chain
from pathlib import Path
from typing import Union, Optional

from mloader.constants import Language
from mloader.response_pb2 import Title, Chapter
from mloader.utils import escape_path, is_oneshot, chapter_name_to_int, is_windows


def _is_extra(chapter_name: str) -> bool:
    """
    Determine if the chapter is marked as extra.

    A chapter is considered extra if its name (after stripping '#' characters)
    equals "ex".

    Parameters:
        chapter_name (str): The raw chapter name.

    Returns:
        bool: True if the chapter is extra, False otherwise.
    """
    return chapter_name.strip("#").lower() == "ex"


class ExporterBase(metaclass=ABCMeta):
    """
    Base class for exporting manga chapters to various formats.

    This abstract class defines common functionality used by concrete exporters,
    including path normalization, chapter naming, and basic file operations.
    Exporters should implement `add_image`, `skip_image`, and the `format` property.
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
        Initialize the exporter with destination path, title/chapter metadata, and options.

        Parameters:
            destination (str): The base directory to save the exported files.
            title (Title): Title metadata from the manga.
            chapter (Chapter): Current chapter metadata.
            next_chapter (Optional[Chapter]): Next chapter metadata, if available.
            add_chapter_title (bool): If True, include the chapter subtitle in the output.
            add_chapter_subdir (bool): If True, create a separate subdirectory for the chapter.
        """
        self.destination = destination

        # Adjust the destination path for Windows (using extended-length path prefix).
        if is_windows():
            resolved_path = Path(self.destination).resolve().as_posix()
            self.destination = f"\\\\?\\{resolved_path}"

        self.add_chapter_title = add_chapter_title
        self.add_chapter_subdir = add_chapter_subdir

        # Clean up and format the manga title.
        self.title_name = escape_path(title.name).title()

        # Add meta data
        self.language = title.language
        self.author = title.author
        self.chapter_title = chapter.sub_title
        self.chapter_number = chapter.name

        # Determine if this is an oneshot and if it is marked as extra.
        self.is_oneshot = is_oneshot(chapter.name, chapter.sub_title)
        self.is_extra = _is_extra(chapter.name)

        # Build extra information strings for naming.
        self._extra_info = []
        if self.is_oneshot:
            self._extra_info.append("[Oneshot]")
        if self.add_chapter_title:
            # Use the escaped version of the chapter subtitle.
            self._extra_info.append(f"[{escape_path(chapter.sub_title)}]")

        # Compute the chapter prefix and suffix for naming.
        self._chapter_prefix = self._format_chapter_prefix(
            self.title_name,
            chapter.name,
            title.language,
            next_chapter.name if next_chapter else None,
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
        """
        Format the prefix for the chapter name based on a naming scheme.

        The prefix includes the title, language (if non-English), and a chapter number
        formatted with a prefix letter and zero-padding. For oneshots, a chapter number of 0
        is used. For extra chapters, the chapter number is derived from the next chapter.

        Parameters:
            title_name (str): Cleaned title name.
            chapter_name (str): The current chapter name.
            language (int): Language code for the title.
            next_chapter_name (Optional[str]): The next chapter name, if available.

        Returns:
            str: The formatted chapter prefix.
        """
        # Start with the title name.
        components = [title_name]

        # Append the language label if not English.
        if Language(language) != Language.ENGLISH:
            components.append(f"[{Language(language).name}]")

        # Append a separator.
        components.append("-")

        # Determine chapter number and prefix letter.
        prefix_letter = ""
        chapter_number = None
        suffix = ""

        if self.is_oneshot:
            chapter_number = 0
        elif self.is_extra and next_chapter_name:
            suffix = "x1"
            chapter_number = chapter_name_to_int(next_chapter_name)
            if chapter_number is not None:
                chapter_number -= 1
                prefix_letter = "c" if chapter_number < 1000 else "d"
        else:
            chapter_number = chapter_name_to_int(chapter_name)
            if chapter_number is not None:
                prefix_letter = "c" if chapter_number < 1000 else "d"

        # Fallback: if chapter_number is None, use an escaped version of the chapter name.
        if chapter_number is None:
            chapter_number = escape_path(chapter_name)
        else:
            # Ensure the chapter number is zero-padded to three digits.
            chapter_number = f"{chapter_number:0>3}"

        # Append the formatted chapter number.
        components.append(f"{prefix_letter}{chapter_number}{suffix}")

        # Append a fixed source label.
        components.append("(web)")
        return " ".join(components)

    def _format_chapter_suffix(self) -> str:
        """
        Format the chapter suffix using extra information and a default marker.

        Returns:
            str: The formatted chapter suffix.
        """
        # Always append "[Unknown]" to indicate an unspecified part.
        return " ".join(chain(self._extra_info, ["[Unknown]"]))

    def _iso_language(self) -> str:
        """
        Convert the stored language into its ISO 639-1 code.

        This method maps the internal `Language` enumeration to the standard
        two-letter ISO 639-1 language codes. If the language is not recognized,
        English (`"en"`) is returned as the default.

        Returns:
            str: The ISO 639-1 language code corresponding to the manga's language.
        """
        language_map = {
            Language.ENGLISH: "en",
            Language.SPANISH: "es",
            Language.FRENCH: "fr",
            Language.INDONESIAN: "id",
            Language.PORTUGUESE: "pt",
            Language.RUSSIAN: "ru",
            Language.THAI: "th",
            Language.GERMAN: "de",
            Language.VIETNAMESE: "vi",
        }

        selected_language = Language(self.language)
        return language_map.get(selected_language, "en")

    def format_page_name(self, page: Union[int, range], ext: str = ".jpg") -> str:
        """
        Format the filename for an individual manga page.

        The page name is constructed from the chapter prefix, page index (or range), and
        the chapter suffix, with the specified file extension.

        Parameters:
            page (Union[int, range]): The page index or a range of page indices.
            ext (str): File extension (default is ".jpg").

        Returns:
            str: The formatted page filename.
        """
        if isinstance(page, range):
            page_str = f"p{page.start:0>3}-{page.stop:0>3}"
        else:
            page_str = f"p{page:0>3}"

        # Remove any leading '.' from the extension.
        ext = ext.lstrip(".")
        return f"{self._chapter_prefix} - {page_str} {self._chapter_suffix}.{ext}"

    def close(self):
        """
        Finalize the export process.

        Concrete exporters may override this method to perform cleanup tasks, such as
        writing buffered data to disk.
        """
        pass

    def __init_subclass__(cls, **kwargs) -> None:
        """
        Automatically register subclasses by their format.

        This method updates the FORMAT_REGISTRY to associate each exporter format with its class.
        """
        cls.FORMAT_REGISTRY[cls.format] = cls
        return super().__init_subclass__(**kwargs)

    @abstractmethod
    def add_image(self, image_data: bytes, index: Union[int, range]):
        """
        Add an image to the export output.

        Parameters:
            image_data (bytes): The raw image data.
            index (Union[int, range]): The index or range for naming the image.
        """
        pass

    @abstractmethod
    def skip_image(self, index: Union[int, range]) -> bool:
        """
        Determine whether an image should be skipped (e.g., already exists).

        Parameters:
            index (Union[int, range]): The index or range of the image.

        Returns:
            bool: True if the image should be skipped, False otherwise.
        """
        pass

    @property
    @abstractmethod
    def format(self) -> str:
        """
        The file format of the exporter (e.g., "raw", "cbz", "pdf").

        Returns:
            str: The exporter format identifier.
        """
        pass
