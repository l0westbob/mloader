"""PDF exporter implementation."""

from __future__ import annotations

import img2pdf
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from PIL import Image

from mloader.__version__ import __title__, __version__
from mloader.exporters.exporter_base import ExporterBase
from mloader.types import ChapterLike, PageIndex, TitleLike


class PDFExporter(ExporterBase):
    """Export manga pages into a PDF file."""

    format = "pdf"

    def __init__(
        self,
        destination: str,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False,
        add_language_to_chapter_name: bool = True,
    ) -> None:
        """Initialize PDF path and disk-backed page buffering state."""
        super().__init__(
            destination=destination,
            title=title,
            chapter=chapter,
            next_chapter=next_chapter,
            add_chapter_title=add_chapter_title,
            add_chapter_subdir=add_chapter_subdir,
            add_language_to_chapter_name=add_language_to_chapter_name,
        )
        base_path = Path(self.destination, self.title_name)
        base_path.mkdir(parents=True, exist_ok=True)
        self.path = base_path.joinpath(self.chapter_name).with_suffix(".pdf")
        self.skip_all_images = self.path.exists()
        self._temp_dir: TemporaryDirectory[str] | None = None
        self._page_paths: list[Path] = []
        if not self.skip_all_images:
            self._temp_dir = TemporaryDirectory(prefix="mloader-pdf-", dir=base_path)

    def add_image(self, image_data: bytes, index: PageIndex) -> None:
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

    def skip_image(self, index: PageIndex) -> bool:
        """Return whether the chapter PDF already exists."""
        _ = index
        return self.skip_all_images

    def _prepare_page_for_pdf(self, page_path: Path, prepared_dir: Path) -> Path:
        """Return a PDF-safe image path, converting unsupported modes to RGB JPEG."""
        with Image.open(page_path) as image:
            if image.mode in {"1", "L", "RGB", "CMYK"}:
                return page_path

            converted = image.convert("RGB")
            converted_path = prepared_dir / f"{page_path.stem}.jpg"
            converted.save(converted_path, format="JPEG", quality=95)
            converted.close()
            return converted_path

    def _build_pdf_inputs(self) -> list[str]:
        """Build ordered image input paths for img2pdf conversion."""
        if self._temp_dir is None:
            return []

        prepared_dir = Path(self._temp_dir.name)
        prepared_paths: list[str] = []
        for page_path in sorted(self._page_paths):
            prepared_paths.append(str(self._prepare_page_for_pdf(page_path, prepared_dir)))
        return prepared_paths

    def close(self) -> None:
        """Write all collected images to the destination PDF file."""
        if self.skip_all_images:
            return

        app_info = f"{__title__} - {__version__}"
        temp_pdf_path: Path | None = None
        try:
            if not self._page_paths:
                return
            pdf_inputs = self._build_pdf_inputs()
            if not pdf_inputs:
                return
            with NamedTemporaryFile(
                "wb",
                delete=False,
                dir=self.path.parent,
                prefix=f".{self.path.stem}.",
                suffix=".tmp",
            ) as output_file:
                temp_pdf_path = Path(output_file.name)
                img2pdf.convert(
                    pdf_inputs,
                    outputstream=output_file,
                    title=self.chapter_name,
                    producer=app_info,
                    creator=app_info,
                )
            temp_pdf_path.replace(self.path)
        finally:
            if temp_pdf_path is not None:
                with suppress(FileNotFoundError):
                    temp_pdf_path.unlink()
            if self._temp_dir is not None:
                self._temp_dir.cleanup()
                self._temp_dir = None
            self._page_paths.clear()

    def discard(self) -> None:
        """Clean buffered page files without publishing a PDF artifact."""
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None
        self._page_paths.clear()
