"""CBZ archive exporter implementation."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

from mloader.exporters.exporter_base import ExporterBase
from mloader.response_pb2 import Chapter, Title  # type: ignore


class CBZExporter(ExporterBase):
    """Export manga pages into a CBZ archive."""

    format = "cbz"

    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
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
        if not self.skip_all_images:
            self.archive_buffer = BytesIO()
            self.archive = zipfile.ZipFile(
                self.archive_buffer,
                mode="w",
                compression=compression,
            )

    def add_image(self, image_data: bytes, index: Union[int, range]) -> None:
        """Write one image into the CBZ archive."""
        if self.skip_all_images:
            return
        image_path = Path(self.chapter_name, self.format_page_name(index))
        self.archive.writestr(image_path.as_posix(), image_data)

    def skip_image(self, index: Union[int, range]) -> bool:
        """Return whether image writes should be skipped."""
        _ = index
        return self.skip_all_images

    def close(self) -> None:
        """Persist the in-memory archive to disk."""
        if self.skip_all_images:
            return
        self.archive.close()
        self.path.write_bytes(self.archive_buffer.getvalue())
