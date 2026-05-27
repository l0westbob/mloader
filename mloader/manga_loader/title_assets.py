"""Title metadata and cover export services."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from io import BytesIO
from pathlib import Path

from PIL import Image

from mloader.domain.manga import TitleDetail
from mloader.domain.requests import CoverFormat
from mloader.manga_loader.chapter_planning import ChapterMetadata
from mloader.utils import escape_path

log = logging.getLogger(__name__)


class MetadataWriter:
    """Write metadata outputs derived from title details."""

    @staticmethod
    def dump_title_metadata(
        title_detail: TitleDetail,
        chapter_data: Mapping[int, ChapterMetadata],
        export_dir: str | Path,
    ) -> None:
        """Write title-level metadata JSON into ``export_dir``."""
        normalized_chapter_data = {
            str(chapter_id): {
                "thumbnail_url": metadata.thumbnail_url,
                "chapter_id": metadata.chapter_id,
                "sub_title": escape_path(metadata.sub_title).title(),
            }
            for chapter_id, metadata in sorted(chapter_data.items())
        }
        export_dir_path = Path(export_dir)
        export_dir_path.mkdir(parents=True, exist_ok=True)

        title_data = {
            "non_appearance_info": title_detail.non_appearance_info,
            "number_of_views": title_detail.number_of_views,
            "overview": title_detail.overview,
            "name": title_detail.title.name,
            "author": title_detail.title.author,
            "portrait_image_url": title_detail.title.portrait_image_url,
            "chapters": normalized_chapter_data,
        }

        metadata_file = export_dir_path / "title_metadata.json"
        with metadata_file.open("w", encoding="utf-8") as file_obj:
            json.dump(title_data, file_obj, ensure_ascii=False, indent=4)


class MetadataExporter:
    """Coordinate title metadata export through the configured writer."""

    @staticmethod
    def dump_title_metadata(
        title_detail: TitleDetail,
        chapter_data: Mapping[int, ChapterMetadata],
        export_dir: str | Path,
    ) -> None:
        """Write title-level metadata JSON into ``export_dir``."""
        MetadataWriter.dump_title_metadata(title_detail, chapter_data, export_dir)


class CoverExporter:
    """Download and persist title cover images."""

    @staticmethod
    def resolve_cover_image_url(title_detail: TitleDetail) -> str | None:
        """Resolve the best available cover URL from title-detail payload data."""
        portrait_cover_url = title_detail.title.portrait_image_url.strip()
        if portrait_cover_url:
            return portrait_cover_url
        primary_cover_url = title_detail.title_image_url.strip()
        if primary_cover_url:
            return primary_cover_url
        landscape_cover_url = title_detail.title.landscape_image_url.strip()
        if landscape_cover_url:
            return landscape_cover_url
        return None

    @staticmethod
    def dump_title_cover(
        title_detail: TitleDetail,
        export_dir: str | Path,
        *,
        cover_format: CoverFormat,
        download_image: Callable[[str], bytes],
    ) -> None:
        """Download and store one title cover image using the selected cover format."""
        cover_url = CoverExporter.resolve_cover_image_url(title_detail)
        if cover_url is None:
            log.warning(
                "    Cover export skipped for '%s': no cover URL found.",
                title_detail.title.name,
            )
            return

        export_dir_path = Path(export_dir)
        export_dir_path.mkdir(parents=True, exist_ok=True)
        cover_path = export_dir_path / f"cover.{cover_format}"
        if cover_path.exists():
            log.info("    Cover for title '%s' already exists.", title_detail.title.name)
            return

        image_blob = download_image(cover_url)
        with Image.open(BytesIO(image_blob)) as image:
            if cover_format == "png":
                converted = image.convert("RGBA")
                converted.save(cover_path, format="PNG")
            elif cover_format == "jpg":
                converted = image.convert("RGB")
                converted.save(cover_path, format="JPEG", quality=95)
            elif cover_format == "webp":
                converted = image.convert("RGBA")
                converted.save(cover_path, format="WEBP", quality=90)
            else:
                raise ValueError(f"Unsupported cover format: {cover_format}")
        log.info("    Cover for title '%s' exported.", title_detail.title.name)
