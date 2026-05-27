"""Single-chapter download orchestration service."""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection
from dataclasses import replace

from mloader.domain.manga import MangaPage, MangaViewer, Title
from mloader.errors import SubscriptionRequiredError
from mloader.manga_loader.manifest import TitleDownloadManifestLike
from mloader.types import ExporterFactoryLike, ExporterLike

log = logging.getLogger(__name__)


class ChapterDownloader:
    """Coordinate one chapter viewer payload through export and manifest tracking."""

    @staticmethod
    def process_chapter(
        *,
        viewer: MangaViewer,
        title: Title,
        chapter_index: int,
        total_chapters: int,
        chapter_id: int,
        output_format: str,
        manifest: TitleDownloadManifestLike | None,
        exporter_factory: ExporterFactoryLike,
        process_pages: Callable[[Collection[MangaPage], str, ExporterLike], None],
        prepare_filename: Callable[[str], str],
    ) -> None:
        """Export one loaded chapter and update manifest state."""
        last_page = viewer.last_page
        if last_page is None:
            raise SubscriptionRequiredError(
                "A MAX subscription is required to download this chapter. "
                "The repository default/free-tier API key can only access free chapters; "
                "provide subscription-capable auth settings for full-catalog downloads."
            )

        current_chapter = last_page.current_chapter
        next_chapter = last_page.next_chapter
        sanitized_chapter = replace(
            current_chapter,
            sub_title=prepare_filename(current_chapter.sub_title),
        )

        log.info(
            f"    {chapter_index}/{total_chapters}) Chapter "
            f"{viewer.chapter_name}: {sanitized_chapter.sub_title}"
        )
        if manifest is not None:
            manifest.mark_started(
                chapter_id,
                chapter_name=viewer.chapter_name,
                sub_title=sanitized_chapter.sub_title,
                output_format=output_format,
            )

        exporter = exporter_factory(
            title=title,
            chapter=sanitized_chapter,
            next_chapter=next_chapter,
        )
        pages = viewer.downloadable_pages
        if not pages:
            raise RuntimeError(
                f"MangaPlus API returned no downloadable pages for chapter {chapter_id}."
            )
        try:
            process_pages(pages, viewer.chapter_name, exporter)
            exporter.close()
        except Exception:
            discard = getattr(exporter, "discard", None)
            if callable(discard):
                discard()
            raise

        if manifest is not None:
            exporter_path = getattr(exporter, "path", None)
            output_path = str(exporter_path) if exporter_path is not None else None
            manifest.mark_completed(chapter_id, output_path=output_path)
