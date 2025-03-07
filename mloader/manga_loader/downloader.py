from itertools import count
import click
import logging
from mloader.constants import PageType

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
        title_detail = self._get_title_details(title_id).title  # Provided by APILoaderMixin.
        log.info(f"{title_index}/{total_titles}) Manga: {title_detail.name}")
        log.info("    Author: %s", title_detail.author)
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