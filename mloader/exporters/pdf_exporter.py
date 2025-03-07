import io
from pathlib import Path
from typing import Union
from PIL import Image
from mloader.exporters.exporter_base import ExporterBase
from mloader.__version__ import __title__, __version__


class PDFExporter(ExporterBase):
    """
    Export manga pages as a PDF document.
    """
    format = "pdf"

    def __init__(self, *args, **kwargs):
        """
        Initialize the PDF exporter and set up output paths.
        """
        super().__init__(*args, **kwargs)
        # Create base directory for the title.
        base_path = Path(self.destination, self.title_name)
        base_path.mkdir(parents=True, exist_ok=True)
        self.path = base_path.joinpath(self.chapter_name).with_suffix(".pdf")
        self.skip_all_images = self.path.exists()
        self.images = []  # List to hold PIL Image objects.

    def add_image(self, image_data: bytes, index: Union[int, range]):
        """
        Add an image to the PDF by opening it with PIL and appending to a list.

        Parameters:
            image_data (bytes): The raw image data.
            index (Union[int, range]): The page index or range.
        """
        if self.skip_all_images:
            return
        # Open the image from bytes and add it to the list.
        self.images.append(Image.open(io.BytesIO(image_data)))

    def skip_image(self, index: Union[int, range]) -> bool:
        """
        Skip adding an image if the PDF file already exists.

        Parameters:
            index (Union[int, range]): The page index or range.

        Returns:
            bool: True if the PDF exists, False otherwise.
        """
        return self.skip_all_images

    def close(self):
        """
        Finalize the PDF export by saving all collected images as a single PDF file.
        """
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