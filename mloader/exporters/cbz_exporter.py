import zipfile
from io import BytesIO
from pathlib import Path
from typing import Union
from mloader.exporters.exporter_base import ExporterBase


class CBZExporter(ExporterBase):
    """
    Export manga pages as a CBZ (Comic Book Zip) archive.
    """
    format = "cbz"

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

    def close(self):
        """
        Finalize the CBZ export by writing the archive to disk.
        """
        if self.skip_all_images:
            return
        self.archive.close()
        # Write the complete archive to the destination file.
        self.path.write_bytes(self.archive_buffer.getvalue())