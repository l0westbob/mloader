"""Single-title download orchestration service."""

from __future__ import annotations

import logging
from contextlib import suppress
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from mloader.domain.manga import Chapter, TitleDetail
from mloader.domain.planning import TitleDownloadPlan
from mloader.manga_loader.chapter_planning import ChapterMetadata
from mloader.domain.requests import FilenameStyle
from mloader.manga_loader.chapter_planning import ChapterPlanner
from mloader.manga_loader.filename_policy import FilenamePolicy
from mloader.manga_loader.manifest import TitleDownloadManifestLike
from mloader.manga_loader.manifest_tracking import ManifestTracker
from mloader.manga_loader.run_report import RunReport

log = logging.getLogger(__name__)

ManifestFactory = Callable[..., TitleDownloadManifestLike]
ProcessChapter = Callable[..., None]


@dataclass(frozen=True, slots=True)
class TitleProcessingOptions:
    """Runtime flags needed while processing one title."""

    destination: str
    cover: bool
    meta: bool
    resume: bool
    manifest_reset: bool
    filename_style: FilenameStyle
    output_format: str
    rename_existing_filenames: bool


@dataclass(frozen=True, slots=True)
class TitleDownloadContext:
    """Collaborators needed to process one title download plan."""

    options: TitleProcessingOptions
    manifest_tracker: type[ManifestTracker]
    manifest_factory: ManifestFactory
    dump_title_cover: Callable[[TitleDetail, Path], None]
    title_detail_with_selected_chapters: Callable[[TitleDetail, Collection[Chapter]], TitleDetail]
    extract_chapter_data: Callable[[TitleDetail], Mapping[int, ChapterMetadata]]
    dump_title_metadata: Callable[[TitleDetail, Mapping[int, ChapterMetadata], Path], None]
    get_existing_files: Callable[[Path], list[str]]
    filter_chapters_to_download: Callable[
        [
            Mapping[int, ChapterMetadata],
            TitleDetail,
            Collection[str],
            Collection[int],
            FilenameStyle,
        ],
        list[int],
    ]
    exclude_manifest_completed_chapters: Callable[
        [Collection[int], TitleDownloadManifestLike], tuple[list[int], int]
    ]
    process_chapter: ProcessChapter
    clear_api_caches_for_title: Callable[[int, Collection[int]], None]


class TitleDownloader:
    """Coordinate title-level export, manifest, and chapter-processing flow."""

    @staticmethod
    def process_title(
        *,
        title_index: int,
        total_titles: int,
        title_plan: TitleDownloadPlan,
        report: RunReport,
        context: TitleDownloadContext,
    ) -> None:
        """Download and export all selected chapters for one title."""
        manifest: TitleDownloadManifestLike | None = None
        options = context.options
        title_detail = title_plan.title_detail
        title = title_detail.title
        chapter_ids = title_plan.chapter_ids
        try:
            log.info(f"{title_index}/{total_titles}) Manga: {title.name}")
            log.info(f"    Author: {title.author}")

            export_path = Path(options.destination) / FilenamePolicy.title_directory_name(
                title.name
            )
            if options.cover:
                try:
                    context.dump_title_cover(title_detail, export_path)
                except Exception as error:
                    log.warning("    Cover export failed for '%s': %s", title.name, error)
            manifest = context.manifest_tracker.prepare_manifest(
                export_path,
                resume=options.resume,
                manifest_reset=options.manifest_reset,
                manifest_factory=context.manifest_factory,
            )

            planned_title_detail = context.title_detail_with_selected_chapters(
                title_detail,
                title_plan.selected_chapters,
            )
            chapter_data = context.extract_chapter_data(planned_title_detail)

            if options.meta:
                context.dump_title_metadata(planned_title_detail, chapter_data, export_path)

            if context.options.rename_existing_filenames:
                _rename_existing_filenames_to_style(
                    export_path=export_path,
                    output_format=context.options.output_format,
                    title_detail=planned_title_detail,
                    chapter_data=chapter_data,
                    filename_style=context.options.filename_style,
                )

            existing_files = context.get_existing_files(export_path)
            chapters_to_download = context.filter_chapters_to_download(
                chapter_data,
                planned_title_detail,
                existing_files,
                chapter_ids,
                context.options.filename_style,
            )
            if options.resume and manifest is not None:
                chapters_to_download, skipped_manifest = (
                    context.exclude_manifest_completed_chapters(
                        chapters_to_download,
                        manifest,
                    )
                )
                report.mark_manifest_skipped(skipped_manifest)

            if not chapters_to_download:
                log.info(f"    All chapters for '{title.name}' are already downloaded.")
                return

            total_chapters = len(chapters_to_download)
            log.info(f"    {total_chapters} chapter(s) to download for '{title.name}'.")
            for chapter_index, chapter_id in enumerate(sorted(chapters_to_download), 1):
                try:
                    context.process_chapter(
                        title_detail,
                        chapter_index,
                        total_chapters,
                        chapter_id,
                        manifest=manifest if options.resume else None,
                    )
                    report.mark_downloaded()
                except KeyboardInterrupt:
                    context.manifest_tracker.mark_failed(
                        manifest,
                        resume=options.resume,
                        chapter_id=chapter_id,
                        error="Interrupted by user.",
                    )
                    report.mark_failed(chapter_id)
                    log.warning("    Interrupted while downloading chapter %s.", chapter_id)
                    raise
                except Exception as error:
                    context.manifest_tracker.mark_failed(
                        manifest,
                        resume=options.resume,
                        chapter_id=chapter_id,
                        error=str(error),
                    )
                    report.mark_failed(chapter_id)
                    log.error("    Failed chapter %s: %s", chapter_id, error)
        finally:
            context.manifest_tracker.flush(manifest, resume=options.resume)
            context.clear_api_caches_for_title(title.title_id, chapter_ids)


def _rename_existing_filenames_to_style(
    *,
    output_format: str,
    export_path: Path,
    title_detail: TitleDetail,
    chapter_data: Mapping[int, ChapterMetadata],
    filename_style: FilenameStyle,
) -> None:
    """Rename legacy filenames to requested style in the title output directory."""
    if output_format not in {"pdf", "cbz"}:
        return

    title_name = FilenamePolicy.title_directory_name(title_detail.title.name)

    for metadata in chapter_data.values():
        chapter = title_detail.find_chapter(metadata.chapter_id)
        if chapter is None:
            continue

        legacy_stem = ChapterPlanner.build_expected_filename_with_style(
            title_name,
            chapter,
            metadata.sub_title,
            title_detail.title.language,
            filename_style="legacy",
        )
        target_stem = ChapterPlanner.build_expected_filename_with_style(
            title_name,
            chapter,
            metadata.sub_title,
            title_detail.title.language,
            filename_style=filename_style,
        )
        if legacy_stem == target_stem:
            continue

        old_path = export_path / f"{legacy_stem}.{output_format}"
        new_path = export_path / f"{target_stem}.{output_format}"
        with suppress(FileNotFoundError, FileExistsError, OSError):
            if old_path.exists() and not new_path.exists():
                old_path.replace(new_path)
