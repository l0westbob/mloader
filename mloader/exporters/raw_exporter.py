"""Raw image exporter implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from mloader.exporters.exporter_base import ExporterBase
from mloader.response_pb2 import Chapter, Title  # type: ignore


class RawExporter(ExporterBase):
    """Export manga pages as standalone image files."""

    format = "raw"

    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
    ) -> None:
        """Initialize output directories for raw image export."""
        super().__init__(
            destination=destination,
            title=title,
            chapter=chapter,
            next_chapter=next_chapter,
            add_chapter_title=add_chapter_title,
            add_chapter_subdir=add_chapter_subdir,
        )
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)

        if self.add_chapter_subdir:
            self.path = self.path.joinpath(self.chapter_name)
            self.path.mkdir(parents=True, exist_ok=True)

    def add_image(self, image_data: bytes, index: Union[int, range]) -> None:
        """Write one page image file to disk."""
        filename = self.format_page_name(index)
        self.path.joinpath(filename).write_bytes(image_data)

    def skip_image(self, index: Union[int, range]) -> bool:
        """Return whether the target image file already exists."""
        filename = self.format_page_name(index)
        return self.path.joinpath(filename).exists()
