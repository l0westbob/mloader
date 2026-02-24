"""Download orchestration logic for titles, chapters, and page assets."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Collection, Literal, Mapping

from mloader.domain.requests import DownloadSummary
from mloader.errors import SubscriptionRequiredError
from mloader.manga_loader.manifest import TitleDownloadManifest
from mloader.manga_loader.services import (
    ChapterMetadata,
    ChapterPlanner,
    MetadataWriter,
    PageExportService,
    PageImageService,
)
from mloader.types import (
    ChapterLike,
    ExporterFactoryLike,
    ExporterLike,
    MangaPageLike,
    MangaViewerLike,
    SessionLike,
    TitleDumpLike,
    TitleLike,
)
from mloader.utils import escape_path

log = logging.getLogger(__name__)


@dataclass(slots=True)
class _MutableDownloadSummary:
    """Mutable run counters used during one download execution."""

    downloaded: int = 0
    skipped_manifest: int = 0
    failed: int = 0
    failed_chapter_ids: list[int] = field(default_factory=list)

    def as_immutable(self) -> DownloadSummary:
        """Build immutable summary payload for public API return value."""
        return DownloadSummary(
            downloaded=self.downloaded,
            skipped_manifest=self.skipped_manifest,
            failed=self.failed,
            failed_chapter_ids=tuple(self.failed_chapter_ids),
        )


class DownloadMixin:
    """Provide download and export orchestration for manga content."""

    meta: bool
    destination: str
    output_format: Literal["raw", "cbz", "pdf"]
    exporter: ExporterFactoryLike
    session: SessionLike
    request_timeout: tuple[float, float]
    resume: bool
    manifest_reset: bool

    def _prepare_normalized_manga_list(
        self,
        title_ids: Collection[int] | None,
        chapter_ids: Collection[int] | None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool,
    ) -> Mapping[int, Collection[int]]:
        """Normalize title/chapter filters into a concrete download mapping."""
        raise NotImplementedError

    def _get_title_details(self, title_id: str | int) -> TitleDumpLike:
        """Load title details for ``title_id``."""
        raise NotImplementedError

    def _load_pages(self, chapter_id: str | int) -> MangaViewerLike:
        """Load chapter viewer payload for ``chapter_id``."""
        raise NotImplementedError

    def _decrypt_image(self, url: str, encryption_hex: str) -> bytearray:
        """Download and decrypt one image payload."""
        raise NotImplementedError

    def _clear_api_caches_for_run(self) -> None:
        """Clear all API cache entries before/after one download run."""

    def _clear_api_caches_for_title(
        self,
        title_id: int,
        chapter_ids: Collection[int],
    ) -> None:
        """Clear per-title API cache entries after title processing."""

    def download(
        self,
        *,
        title_ids: Collection[int] | None = None,
        chapter_ids: Collection[int] | None = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> DownloadSummary:
        """Start a download run using already validated filters."""
        summary = _MutableDownloadSummary()
        self._clear_api_caches_for_run()
        try:
            normalized_mapping = self._prepare_normalized_manga_list(
                title_ids,
                chapter_ids,
                min_chapter,
                max_chapter,
                last_chapter,
            )
            self._download(normalized_mapping, summary)
        finally:
            self._clear_api_caches_for_run()
        return summary.as_immutable()

    def _download(
        self,
        manga_mapping: Mapping[int, Collection[int]],
        summary: _MutableDownloadSummary,
    ) -> None:
        """Iterate through normalized titles and process them one by one."""
        total_titles = len(manga_mapping)
        for title_index, (title_id, chapter_ids) in enumerate(manga_mapping.items(), 1):
            self._process_title(title_index, total_titles, title_id, chapter_ids, summary=summary)

    def _process_title(
        self,
        title_index: int,
        total_titles: int,
        title_id: int,
        chapter_ids: Collection[int],
        *,
        summary: _MutableDownloadSummary,
    ) -> None:
        """Download and export all selected chapters for one title."""
        manifest: TitleDownloadManifest | None = None
        try:
            title_dump = self._get_title_details(title_id)
            title_detail = title_dump.title

            log.info(f"{title_index}/{total_titles}) Manga: {title_detail.name}")
            log.info(f"    Author: {title_detail.author}")

            export_path = Path(self.destination) / escape_path(title_detail.name).title()
            if self.resume or self.manifest_reset:
                manifest = TitleDownloadManifest(export_path, autosave=False)
                if self.manifest_reset:
                    manifest.reset()

            chapter_data = self._extract_chapter_data(title_dump)

            if self.meta:
                self._dump_title_metadata(title_dump, chapter_data, export_path)

            existing_files = self._get_existing_files(export_path)
            chapters_to_download = self._filter_chapters_to_download(
                chapter_data,
                title_dump,
                title_detail,
                existing_files,
                chapter_ids,
            )
            if self.resume and manifest is not None:
                chapters_to_download, skipped_manifest = self._exclude_manifest_completed_chapters(
                    chapters_to_download,
                    manifest,
                )
                summary.skipped_manifest += skipped_manifest

            if not chapters_to_download:
                log.info(f"    All chapters for '{title_detail.name}' are already downloaded.")
                return

            total_chapters = len(chapters_to_download)
            log.info(f"    {total_chapters} chapter(s) to download for '{title_detail.name}'.")
            for chapter_index, chapter_id in enumerate(sorted(chapters_to_download), 1):
                try:
                    self._process_chapter(
                        title_detail,
                        chapter_index,
                        total_chapters,
                        chapter_id,
                        manifest=manifest if self.resume else None,
                    )
                    summary.downloaded += 1
                except Exception as error:
                    if self.resume and manifest is not None:
                        manifest.mark_failed(chapter_id, error=str(error))
                        manifest.flush()
                    summary.failed += 1
                    summary.failed_chapter_ids.append(chapter_id)
                    log.error("    Failed chapter %s: %s", chapter_id, error)
        finally:
            if self.resume and manifest is not None:
                manifest.flush()
            self._clear_api_caches_for_title(title_id, chapter_ids)

    def _process_chapter(
        self,
        title_detail: TitleLike,
        chapter_index: int,
        total_chapters: int,
        chapter_id: int,
        *,
        manifest: TitleDownloadManifest | None = None,
    ) -> None:
        """Download and export a single chapter."""
        viewer = self._load_pages(chapter_id)
        if not self._has_last_page(viewer):
            raise SubscriptionRequiredError("A MAX subscription is required to download this chapter.")

        last_page = viewer.pages[-1].last_page
        current_chapter = last_page.current_chapter
        next_chapter = (
            last_page.next_chapter if last_page.next_chapter.chapter_id != 0 else None
        )

        current_chapter.sub_title = self._prepare_filename(current_chapter.sub_title)
        log.info(
            f"    {chapter_index}/{total_chapters}) Chapter "
            f"{viewer.chapter_name}: {current_chapter.sub_title}"
        )
        if manifest is not None:
            manifest.mark_started(
                chapter_id,
                chapter_name=viewer.chapter_name,
                sub_title=current_chapter.sub_title,
                output_format=self.output_format,
            )

        exporter = self.exporter(
            title=title_detail,
            chapter=current_chapter,
            next_chapter=next_chapter,
        )
        pages = [page.manga_page for page in viewer.pages if page.manga_page.image_url]
        self._process_chapter_pages(pages, viewer.chapter_name, exporter)
        exporter.close()

        if manifest is not None:
            exporter_path = getattr(exporter, "path", None)
            output_path = str(exporter_path) if exporter_path is not None else None
            manifest.mark_completed(chapter_id, output_path=output_path)

    def _process_chapter_pages(
        self,
        pages: Collection[MangaPageLike],
        chapter_name: str,
        exporter: ExporterLike,
    ) -> None:
        """Download all chapter pages and pass them to the exporter."""
        PageExportService.export_pages(
            pages,
            chapter_name,
            exporter,
            fetch_page_image=self._fetch_page_image,
        )

    def _download_image(self, url: str) -> bytes:
        """Download an image blob from ``url``."""
        return PageImageService.download_image(
            self.session,
            self.request_timeout,
            url,
        )

    def _fetch_page_image(self, page: MangaPageLike) -> bytes:
        """Return raw or decrypted image bytes for one manga page."""
        return PageImageService.fetch_page_image(
            page,
            download_image=self._download_image,
            decrypt_image=self._decrypt_image,
        )

    def _dump_title_metadata(
        self,
        title_dump: TitleDumpLike,
        chapter_data_or_export_dir: Mapping[int, ChapterMetadata | Mapping[str, object]] | str | Path,
        export_dir: str | Path | None = None,
    ) -> None:
        """Write title-level metadata JSON into ``export_dir``."""
        resolved_chapter_data: Mapping[int, ChapterMetadata | Mapping[str, object]]
        resolved_export_dir: str | Path
        if export_dir is None:
            if isinstance(chapter_data_or_export_dir, Mapping):
                raise TypeError("Expected export directory when chapter metadata is omitted.")
            resolved_chapter_data = self._extract_chapter_data(title_dump)
            resolved_export_dir = chapter_data_or_export_dir
        else:
            if not isinstance(chapter_data_or_export_dir, Mapping):
                raise TypeError("Expected chapter metadata mapping when export_dir is provided.")
            resolved_chapter_data = chapter_data_or_export_dir
            resolved_export_dir = export_dir

        MetadataWriter.dump_title_metadata(title_dump, resolved_chapter_data, resolved_export_dir)
        log.info(f"    Metadata for title '{title_dump.title.name}' exported")

    def _extract_chapter_data(self, title_dump: TitleDumpLike) -> dict[int, ChapterMetadata]:
        """Collect chapter metadata from all chapter groups into one mapping."""
        return ChapterPlanner.extract_chapter_data(title_dump, self._prepare_filename)

    def _get_existing_files(self, export_path: Path) -> list[str]:
        """Return existing chapter stems for single-file output formats."""
        if not export_path.exists():
            return []

        extension = self._chapter_output_extension()
        if extension is None:
            return []

        existing_files = [file.stem for file in export_path.glob(f"*.{extension}")]
        log.info(f"    Found {len(existing_files)} existing chapter files in '{export_path}'.")
        log.debug(f"    Existing files: {existing_files}")
        return existing_files

    def _chapter_output_extension(self) -> str | None:
        """Return chapter-level output extension, or ``None`` for raw image mode."""
        if self.output_format in {"pdf", "cbz"}:
            return self.output_format
        return None

    def _filter_chapters_to_download(
        self,
        chapter_data: Mapping[int, ChapterMetadata],
        title_dump: TitleDumpLike,
        title_detail: TitleLike,
        existing_files: Collection[str],
        requested_chapter_ids: Collection[int],
    ) -> list[int]:
        """Return chapter IDs that are requested and not already exported."""
        return ChapterPlanner.filter_chapters_to_download(
            chapter_data,
            title_dump,
            title_detail,
            existing_files,
            requested_chapter_ids,
        )

    def _exclude_manifest_completed_chapters(
        self,
        chapter_ids: Collection[int],
        manifest: TitleDownloadManifest,
    ) -> tuple[list[int], int]:
        """Exclude chapter IDs already marked completed in the title manifest."""
        pending = [chapter_id for chapter_id in chapter_ids if not manifest.is_completed(chapter_id)]
        skipped_count = len(chapter_ids) - len(pending)
        if skipped_count:
            log.info(f"    Skipping {skipped_count} chapter(s) already marked completed in manifest.")
        return pending, skipped_count

    def _build_expected_filename(
        self,
        title_name: str,
        chapter_obj: ChapterLike,
        sub_title: str,
    ) -> str:
        """Build normalized filename stem expected for chapter-level outputs."""
        del self
        return ChapterPlanner.build_expected_filename(title_name, chapter_obj, sub_title)

    def _find_chapter_by_id(self, title_dump: TitleDumpLike, chapter_id: int) -> ChapterLike | None:
        """Find and return a chapter object by ``chapter_id`` if available."""
        return ChapterPlanner.find_chapter_by_id(title_dump, chapter_id)

    def _has_last_page(self, viewer: MangaViewerLike) -> bool:
        """Return whether ``viewer`` includes a valid terminal page payload."""
        return bool(viewer.pages and viewer.pages[-1] and hasattr(viewer.pages[-1], "last_page"))

    def _prepare_filename(self, text: str) -> str:
        """Fix common encoding glitches and sanitize text for filesystem use."""
        fixed_text = text
        try:
            fixed_text = text.encode("latin1").decode("utf8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            log.warning(f"    Encoding fix skipped for: {text}")
        return escape_path(fixed_text)
