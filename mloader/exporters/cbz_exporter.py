"""CBZ archive exporter implementation."""

from __future__ import annotations

from contextlib import suppress
from html import escape
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

from mloader.exporters.exporter_base import ExporterBase
from mloader.types import ChapterLike, PageIndex, TitleLike


class CBZExporter(ExporterBase):
    """Export manga pages into a CBZ archive."""

    format = "cbz"
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

    def __init__(
        self,
        destination: str,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
        compression: int = zipfile.ZIP_DEFLATED,
    ) -> None:
        """Initialize archive path and optional in-memory zip buffer."""
        super().__init__(
            destination=destination,
            title=title,
            chapter=chapter,
            next_chapter=next_chapter,
            add_chapter_title=add_chapter_title,
            add_chapter_subdir=add_chapter_subdir,
        )
        base_path = Path(self.destination, self.title_name)
        base_path.mkdir(parents=True, exist_ok=True)
        self.path = base_path.joinpath(self.chapter_name).with_suffix(".cbz")

        self.skip_all_images = self.path.exists()
        self._temp_path: Path | None = None
        if not self.skip_all_images:
            with NamedTemporaryFile(
                "wb",
                delete=False,
                dir=self.path.parent,
                prefix=f".{self.path.stem}.",
                suffix=".tmp",
            ) as tmp:
                self._temp_path = Path(tmp.name)
            self.archive = zipfile.ZipFile(
                self._temp_path,
                mode="w",
                compression=compression,
            )

    def add_image(self, image_data: bytes, index: PageIndex) -> None:
        """Write one image into the CBZ archive."""
        if self.skip_all_images:
            return
        image_path = Path(self.chapter_name, self.format_page_name(index))
        self.archive.writestr(image_path.as_posix(), image_data)

    def skip_image(self, index: PageIndex) -> bool:
        """Return whether image writes should be skipped."""
        _ = index
        return self.skip_all_images

    def _generate_comicinfo_xml(self) -> str:
        """Generate a ComicInfo.xml payload for the current chapter export."""
        return self.COMICINFO_XML_TEMPLATE.format(
            series=escape(self.series_name or ""),
            number=escape(str(self.chapter_number or "")),
            title=escape(self.chapter_title or ""),
            writer=escape(self.author or ""),
            language_iso=escape(self._iso_language()),
        )

    def _write_comicinfo_xml_entry(self) -> None:
        """Write ComicInfo.xml into the chapter directory inside the CBZ archive."""
        xml_path = Path(self.chapter_name, "ComicInfo.xml").as_posix()
        with suppress(Exception):
            if xml_path in self.archive.namelist():
                return

        self.archive.writestr(xml_path, self._generate_comicinfo_xml())

    def close(self) -> None:
        """Atomically persist the disk-backed archive with ComicInfo metadata."""
        if self.skip_all_images:
            return

        replaced = False
        try:
            try:
                self._write_comicinfo_xml_entry()
            finally:
                with suppress(Exception):
                    self.archive.close()
            if self._temp_path is None:
                return
            self._temp_path.replace(self.path)
            replaced = True
            self.skip_all_images = True
        finally:
            if not replaced and self._temp_path is not None:
                with suppress(FileNotFoundError):
                    self._temp_path.unlink()
            self._temp_path = None

    def discard(self) -> None:
        """Clean a partially written temporary archive without publishing it."""
        if self.skip_all_images:
            return

        with suppress(Exception):
            self.archive.close()
        if self._temp_path is not None:
            with suppress(FileNotFoundError):
                self._temp_path.unlink()
        self._temp_path = None
