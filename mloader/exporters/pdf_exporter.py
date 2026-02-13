"""PDF exporter implementation."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

from PIL import Image

from mloader.__version__ import __title__, __version__
from mloader.exporters.exporter_base import ExporterBase
from mloader.response_pb2 import Chapter, Title  # type: ignore


class PDFExporter(ExporterBase):
    """Export manga pages into a PDF file."""

    format = "pdf"

    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
    ) -> None:
        """Initialize PDF path and buffered image collection."""
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
        self.path = base_path.joinpath(self.chapter_name).with_suffix(".pdf")
        self.skip_all_images = self.path.exists()
        self.images: list[Image.Image] = []

    def add_image(self, image_data: bytes, index: Union[int, range]) -> None:
        """Append one image to the PDF image list."""
        _ = index
        if self.skip_all_images:
            return
        self.images.append(Image.open(io.BytesIO(image_data)))

    def skip_image(self, index: Union[int, range]) -> bool:
        """Return whether the chapter PDF already exists."""
        _ = index
        return self.skip_all_images

    def close(self) -> None:
        """Write all collected images to the destination PDF file."""
        if self.skip_all_images or not self.images:
            return

        app_info = f"{__title__} - {__version__}"
        self.images[0].save(
            self.path,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=self.images[1:],
            title=self.chapter_name,
            producer=app_info,
            creator=app_info,
        )
