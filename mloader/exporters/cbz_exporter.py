"""CBZ archive exporter implementation."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from html import escape
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

from mloader.exporters.exporter_base import ExporterBase
from mloader.types import ChapterLike, PageIndex, TitleLike


class CBZExporter(ExporterBase):
    """Export manga pages into a CBZ archive."""

    format = "cbz"

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
        self.summary = str(getattr(title, "overview", "") or "")
        self.web_url = str(getattr(title, "web_url", "") or "")
        self.tags = tuple(getattr(title, "tags", ()) or ())
        self._page_count = 0

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
        self.archive.writestr(self.format_page_name(index), image_data)
        self._page_count += 1

    def skip_image(self, index: PageIndex) -> bool:
        """Return whether image writes should be skipped."""
        _ = index
        return self.skip_all_images

    def _generate_comicinfo_xml(self) -> str:
        """Generate a ComicInfo.xml payload for the current chapter export."""
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            "<ComicInfo>",
            self._comicinfo_element("Series", self.series_name or ""),
            self._comicinfo_element("Number", str(self.chapter_number or "")),
            self._comicinfo_element("Title", self.chapter_title or ""),
            self._comicinfo_element("Writer", self.author or ""),
            self._comicinfo_element("LanguageISO", self._iso_language()),
            self._comicinfo_element("Manga", "YesAndRightToLeft"),
            self._comicinfo_element("Publisher", "Shueisha"),
            self._comicinfo_element("Format", "Digital"),
        ]
        lines.extend(self._comicinfo_date_elements())
        lines.extend(self._optional_comicinfo_element("Summary", self.summary))
        lines.extend(self._optional_comicinfo_element("Web", self.web_url))
        lines.extend(self._optional_comicinfo_element("PageCount", str(self._page_count)))
        tag_names = self._tag_names()
        genre_value = ", ".join(tag_names) if tag_names else "Manga"
        lines.append(self._comicinfo_element("Genre", genre_value))
        if tag_names:
            lines.append(self._comicinfo_element("Tags", ", ".join(tag_names)))
        lines.append("</ComicInfo>")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _comicinfo_element(name: str, value: str) -> str:
        """Return an escaped ComicInfo element line."""
        return f"    <{name}>{escape(value)}</{name}>"

    def _optional_comicinfo_element(self, name: str, value: str) -> list[str]:
        """Return one optional ComicInfo element when ``value`` is non-empty."""
        if not value:
            return []
        return [self._comicinfo_element(name, value)]

    def _comicinfo_date_elements(self) -> list[str]:
        """Return ComicInfo release-date elements from the chapter timestamp."""
        start_timestamp = int(getattr(self.chapter, "start_timestamp", 0) or 0)
        if start_timestamp <= 0:
            return []
        release_date = datetime.fromtimestamp(start_timestamp, UTC)
        return [
            self._comicinfo_element("Year", str(release_date.year)),
            self._comicinfo_element("Month", str(release_date.month)),
            self._comicinfo_element("Day", str(release_date.day)),
        ]

    def _tag_names(self) -> tuple[str, ...]:
        """Return non-empty MangaPlus tag display names in API order."""
        return tuple(
            tag_name
            for tag in self.tags
            if (tag_name := str(getattr(tag, "name", "") or ""))
        )

    def _write_comicinfo_xml_entry(self) -> None:
        """Write ComicInfo.xml at the root of the CBZ archive."""
        xml_path = "ComicInfo.xml"
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
