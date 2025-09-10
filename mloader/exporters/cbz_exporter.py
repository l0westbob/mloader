import zipfile
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Union
from tempfile import NamedTemporaryFile
from contextlib import suppress

from mloader.exporters.exporter_base import ExporterBase


class CBZExporter(ExporterBase):
    """
    Export manga pages as a CBZ (Comic Book Zip) archive.
    """
    format = "cbz"

    # Class-level template to avoid embedding a large literal directly in the return statement.
    # Using named placeholders keeps it readable and easy to maintain.
    COMICINFO_XML_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<ComicInfo>
    <Series>{series}</Series>
    <Number>{number}</Number>
    <Title>{title}</Title>
    <Writer>{writer}</Writer>
    <LanguageISO>{language_iso}</LanguageISO>
    <Manga>YesAndRightToLeft</Manga>
    <Publisher>Shueisha</Publisher>
    <Genre>Manga</Genre>
</ComicInfo>
"""

    def __init__(self, compression=zipfile.ZIP_DEFLATED, *args, **kwargs):
        """
        Initialize the CBZ exporter with ZIP compression and prepare the archive.

        Parameters:
            compression: The ZIP compression mode (default is ZIP_DEFLATED).
        """
        super().__init__(*args, **kwargs)
        # Create base directory and determine the output CBZ file path.
        base_path = Path(self.destination, self.title_name)
        base_path.mkdir(parents=True, exist_ok=True)
        self.path = base_path.joinpath(self.chapter_name).with_suffix(".cbz")

        # Check if the archive already exists.
        self.skip_all_images = self.path.exists()
        if not self.skip_all_images:
            # Use an in-memory buffer to build the archive, then write to disk.
            self.archive_buffer = BytesIO()
            self.archive = zipfile.ZipFile(
                self.archive_buffer, mode="w", compression=compression
            )

    def _generate_comicinfo_xml(self) -> str:
        """
        Generate a basic ComicInfo.xml metadata file.
        See: https://github.com/anansi-project/comicinfo

        Returns:
            str: The ComicInfo.xml content as a string.

        Notes:
            - Values are XML-escaped to ensure the output is well-formed even if
              metadata contains special characters (e.g., '&', '<', '>').
            - The language code is derived from the base class via `_iso_language()`.
        """
        return self.COMICINFO_XML_TEMPLATE.format(
            series=escape(self.title_name or ""),
            number=escape(str(self.chapter_number or "")),
            title=escape(self.chapter_title or ""),
            writer=escape(self.author or ""),
            language_iso=escape(self._iso_language()),
        )

    def _write_comicinfo_xml_entry(self) -> None:
        """
        Write the ComicInfo.xml entry into the in-memory ZIP archive.

        This function centralizes creation of the internal path and the actual write, so
        the `close()` method can stay small and focused on finalization/IO concerns.
        """
        xml_content = self._generate_comicinfo_xml()
        xml_path = Path(self.chapter_name, "ComicInfo.xml").as_posix()

        # Avoid duplicate entries if called twice by guarding on existing names.
        # Duplicate names in a ZIP are technically allowed but undesirable.
        with suppress(Exception):
            if xml_path in self.archive.namelist():
                return

        self.archive.writestr(xml_path, xml_content)

    def add_image(self, image_data: bytes, index: Union[int, range]):
        """
        Add an image to the CBZ archive.

        Parameters:
            image_data (bytes): The raw image data.
            index (Union[int, range]): The page index or range.
        """
        if self.skip_all_images:
            return
        # Create an internal path for the image inside the archive.
        image_path = Path(self.chapter_name, self.format_page_name(index))
        self.archive.writestr(image_path.as_posix(), image_data)

    def skip_image(self, index: Union[int, range]) -> bool:
        """
        Always skip image addition if the archive file already exists.

        Parameters:
            index (Union[int, range]): The page index or range.

        Returns:
            bool: True if the archive exists, False otherwise.
        """
        return self.skip_all_images

    def close(self) -> None:
        """
        Finalize the CBZ export by writing the archive to disk.

        Improvements over the initial version:
            - Writes ComicInfo.xml via a dedicated helper for testability and separation of concerns.
            - Ensures the ZipFile is closed even if something goes wrong while writing metadata.
            - Uses an atomic file write (temp file + replace) to avoid partial files on disk.
        """
        if self.skip_all_images:
            return

        try:
            # Generate and write ComicInfo.xml to the archive (once).
            self._write_comicinfo_xml_entry()
        finally:
            # Ensure the archive handle is closed even if writestr fails.
            with suppress(Exception):
                self.archive.close()

        # Atomically write to the destination for robustness against partial writes.
        data = self.archive_buffer.getvalue()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("wb", delete=False, dir=self.path.parent) as tmp:
            tmp.write(data)
            temp_path = Path(tmp.name)

        # Replace is atomic on the same filesystem.
        temp_path.replace(self.path)
