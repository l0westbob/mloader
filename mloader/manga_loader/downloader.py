from itertools import count
import click
import logging
from mloader.constants import PageType
import json
from pathlib import Path

log = logging.getLogger(__name__)


class DownloadMixin:
    def download(
            self,
            *,
            title_ids=None,
            chapter_ids=None,
            min_chapter: int,
            max_chapter: int,
            last_chapter: bool = False,
    ):
        """
        Start the manga download process using the provided filtering parameters.

        Parameters:
            title_ids (Optional[Collection[int]]): Collection of manga title IDs.
            chapter_ids (Optional[Collection[int]]): Collection of specific chapter IDs.
            min_chapter (int): Minimum chapter number to include.
            max_chapter (int): Maximum chapter number to include.
            last_chapter (bool): If True, only download the last chapter of each title.
        """
        normalized_mapping = self._prepare_normalized_manga_list(
            title_ids, chapter_ids, min_chapter, max_chapter, last_chapter
        )
        self._download(normalized_mapping)

    def _download(self, manga_mapping):
        """
        Download and export manga chapters based on the normalized mapping.

        Parameters:
            manga_mapping: Mapping of title IDs to sets of chapter IDs.
        """
        total_titles = len(manga_mapping)
        for title_index, (title_id, chapter_ids) in enumerate(manga_mapping.items(), 1):
            self._process_title(title_index, total_titles, title_id, chapter_ids)

    def _process_title(self, title_index, total_titles, title_id, chapter_ids):
        """
        Process all chapters for a single manga title.

        Parameters:
            title_index (int): Index of the current manga title.
            total_titles (int): Total number of manga titles.
            title_id: Unique identifier for the manga title.
            chapter_ids: Collection of chapter IDs for the title.
        """
        title_dump = self._get_title_details(title_id)
        title_detail = title_dump.title

        log.info(f"{title_index}/{total_titles}) Manga: {title_detail.name}")
        log.info("    Author: %s", title_detail.author)

        if self.meta:
            export_path = f"{self.exporter.keywords['destination']}/{title_detail.name}"
            self._dump_title_metadata(title_dump, export_path)

        total_chapters = len(chapter_ids)
        for chapter_index, chapter_id in enumerate(sorted(chapter_ids), 1):
            self._process_chapter(title_detail, chapter_index, total_chapters, chapter_id)

    def _process_chapter(self, title_detail, chapter_index, total_chapters, chapter_id):
        """
        Process a single chapter: load pages, log details, and download images.

        Parameters:
            title_detail: Object containing the manga title details.
            chapter_index (int): The chapter's index for logging.
            total_chapters (int): Total number of chapters for the title.
            chapter_id: Unique identifier for the chapter.
        """
        viewer = self._load_pages(chapter_id)  # Provided by APILoaderMixin.

        # Check if we have the expected last_page attribute. If not, assume a MAX subscription is needed.
        if not viewer.pages or viewer.pages[-1] is None or not hasattr(viewer.pages[-1], 'last_page'):
            log.info("A MAX subscription is required to download this chapter.")
            import sys
            sys.exit(1)

        last_page = viewer.pages[-1].last_page
        current_chapter = last_page.current_chapter
        next_chapter = last_page.next_chapter if last_page.next_chapter.chapter_id != 0 else None
        chapter_name = viewer.chapter_name
        log.info(
            f"    {chapter_index}/{total_chapters}) Chapter {chapter_name}: {current_chapter.sub_title}"
        )

        exporter = self.exporter(title=title_detail, chapter=current_chapter, next_chapter=next_chapter)
        pages = [page.manga_page for page in viewer.pages if page.manga_page.image_url]
        self._process_chapter_pages(pages, chapter_name, exporter)
        exporter.close()

    def _process_chapter_pages(self, pages, chapter_name, exporter):
        """
        Download and export images for all pages in a chapter with progress indication.

        Parameters:
            pages (List): List of page objects that contain image URLs.
            chapter_name (str): The chapter's name used for labeling the progress bar.
            exporter: An exporter instance to handle the downloaded images.
        """
        with click.progressbar(pages, label=chapter_name, show_pos=True) as progress_bar:
            page_counter = count()
            for page_index, page in zip(page_counter, progress_bar):
                # Adjust page index for double-page types.
                if PageType(page.type) == PageType.DOUBLE:
                    page_index = range(page_index, next(page_counter))
                if not exporter.skip_image(page_index):
                    image_blob = self._download_image(page.image_url)
                    exporter.add_image(image_blob, page_index)

    def _download_image(self, url: str) -> bytes:
        """
        Download an image from the specified URL.

        Parameters:
            url (str): The URL of the image to download.

        Returns:
            bytes: The binary data of the downloaded image.
        """
        response = self.session.get(url)
        response.raise_for_status()  # Raises an error for bad responses.
        return response.content

    def _dump_title_metadata(self, title_dump, export_dir):
        """
        Dump title metadata to a JSON file in the given export directory.

        Parameters:
            title_dump (TitleDetailView): The protobuf title details object.
            export_dir (str or Path): The directory where the JSON will be saved.
        """

        chapter_groups = title_dump.chapter_list_group  # This is fine!

        chapter_data = {}

        for group in chapter_groups:
            for chapter in group.first_chapter_list:
                chapter_data[chapter.sub_title] = {
                    "thumbnail_url": chapter.thumbnail_url
                }

            for chapter in group.mid_chapter_list:
                chapter_data[chapter.sub_title] = {
                    "thumbnail_url": chapter.thumbnail_url
                }

            for chapter in group.last_chapter_list:
                chapter_data[chapter.sub_title] = {
                    "thumbnail_url": chapter.thumbnail_url
                }

        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Extract the fields you want
        title_data = {
            "non_appearance_info": title_dump.non_appearance_info,
            "number_of_views": title_dump.number_of_views,
            "overview": title_dump.overview,
            "name": title_dump.title.name,
            "author": title_dump.title.author,
            "portrait_image_url": title_dump.title.portrait_image_url,
            "chapters": chapter_data,
        }

        # JSON file path
        metadata_file = export_dir / "title_metadata.json"

        # Write the JSON file
        with metadata_file.open('w', encoding='utf-8') as f:
            json.dump(title_data, f, ensure_ascii=False, indent=4)

        log.info(f"    Metadata for title '{title_data['name']}' exported")