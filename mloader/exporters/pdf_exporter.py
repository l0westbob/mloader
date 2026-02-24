"""PDF exporter implementation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
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
        """Initialize PDF path and disk-backed page buffering state."""
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
        self._temp_dir: TemporaryDirectory[str] | None = None
        self._page_paths: list[Path] = []
        if not self.skip_all_images:
            self._temp_dir = TemporaryDirectory(prefix="mloader-pdf-", dir=base_path)

    def add_image(self, image_data: bytes, index: Union[int, range]) -> None:
        """Persist one image payload into a temporary page buffer file."""
        if self.skip_all_images:
            return
        if self._temp_dir is None:
            return

        if isinstance(index, range):
            sort_key = index.start
        else:
            sort_key = index
        page_path = Path(self._temp_dir.name) / f"{sort_key:08d}.img"
        page_path.write_bytes(image_data)
        self._page_paths.append(page_path)

    def skip_image(self, index: Union[int, range]) -> bool:
        """Return whether the chapter PDF already exists."""
        _ = index
        return self.skip_all_images

    def close(self) -> None:
        """Write all collected images to the destination PDF file."""
        if self.skip_all_images or not self._page_paths:
            return

        app_info = f"{__title__} - {__version__}"
        opened_images: list[Image.Image] = []
        try:
            for page_path in sorted(self._page_paths):
                opened_image: Image.Image = Image.open(page_path)
                if opened_image.mode != "RGB":
                    converted = opened_image.convert("RGB")
                    opened_image.close()
                    opened_image = converted
                opened_images.append(opened_image)

            opened_images[0].save(
                self.path,
                "PDF",
                resolution=100.0,
                save_all=True,
                append_images=opened_images[1:],
                title=self.chapter_name,
                producer=app_info,
                creator=app_info,
            )
        finally:
            for image in opened_images:
                image.close()
            if self._temp_dir is not None:
                self._temp_dir.cleanup()
                self._temp_dir = None
            self._page_paths.clear()
