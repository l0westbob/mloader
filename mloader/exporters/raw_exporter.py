from pathlib import Path
from typing import Union
from mloader.exporters.exporter_base import ExporterBase


class RawExporter(ExporterBase):
    """
    Export manga pages as raw image files to the filesystem.
    """
    format = "raw"

    def __init__(self, *args, **kwargs):
        """
        Initialize the raw exporter and create necessary directories.
        """
        super().__init__(*args, **kwargs)
        # Create base directory for the title.
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)

        # Optionally create a subdirectory for the chapter.
        if self.add_chapter_subdir:
            self.path = self.path.joinpath(self.chapter_name)
            self.path.mkdir(parents=True, exist_ok=True)

    def add_image(self, image_data: bytes, index: Union[int, range]):
        """
        Write a single image to the filesystem.

        Parameters:
            image_data (bytes): The raw image data.
            index (Union[int, range]): The page index or range.
        """
        filename = self.format_page_name(index)
        file_path = self.path.joinpath(filename)
        file_path.write_bytes(image_data)

    def skip_image(self, index: Union[int, range]) -> bool:
        """
        Skip an image if the file already exists.

        Parameters:
            index (Union[int, range]): The page index or range.

        Returns:
            bool: True if the file exists and should be skipped.
        """
        filename = self.format_page_name(index)
        return self.path.joinpath(filename).exists()