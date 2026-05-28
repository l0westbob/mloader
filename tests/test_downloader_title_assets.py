"""Tests for downloader title metadata and cover asset export."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest
from PIL import Image

from mloader.domain.requests import CoverFormat
from mloader.manga_loader.chapter_planning import ChapterMetadata, ChapterPlanner
from mloader.manga_loader.filename_policy import FilenamePolicy
from mloader.manga_loader.title_assets import CoverExporter, MetadataExporter
from tests.downloader_helpers import (
    chapter as _chapter,
    title_detail as _title_detail,
)


def test_dump_title_metadata_writes_expected_json(tmp_path: Path) -> None:
    """Verify metadata exporter writes normalized chapter metadata JSON."""
    title_detail = _title_detail(
        name="my manga",
        author="author",
        portrait_image_url="http://img",
        number_of_views=321,
        chapters=[_chapter(1, "#1", "hello/world", thumbnail_url="t1")],
    )

    export_dir = tmp_path / "My Manga"
    chapter_data = ChapterPlanner.extract_chapter_data(
        title_detail,
        FilenamePolicy.prepare_filename,
    )
    MetadataExporter.dump_title_metadata(title_detail, chapter_data, export_dir)

    metadata_file = export_dir / "title_metadata.json"
    assert metadata_file.exists()

    content = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert content["name"] == "my manga"
    assert content["author"] == "author"
    assert content["chapters"]["1"]["chapter_id"] == 1
    assert content["chapters"]["1"]["sub_title"] == "Hello World"


def test_dump_title_metadata_supports_explicit_chapter_mapping(tmp_path: Path) -> None:
    """Verify explicit ``chapter_data`` + ``export_dir`` writes metadata output."""
    title_detail = _title_detail(
        name="my manga",
        author="author",
        portrait_image_url="http://img",
        number_of_views=1,
        chapters=[],
    )
    chapter_data = {1024959: ChapterMetadata(thumbnail_url="t1", chapter_id=1024959, sub_title="A")}
    export_dir = tmp_path / "My Manga"

    MetadataExporter.dump_title_metadata(title_detail, chapter_data, export_dir)

    content = json.loads((export_dir / "title_metadata.json").read_text(encoding="utf-8"))
    assert content["chapters"]["1024959"]["chapter_id"] == 1024959
    assert content["chapters"]["1024959"]["sub_title"] == "A"


def test_resolve_cover_image_url_prefers_portrait_and_falls_back_to_main() -> None:
    """Verify cover URL resolution prefers portrait image URL over title image URL."""
    with_main = _title_detail(
        title_image_url="https://img/main.webp",
        portrait_image_url="https://img/portrait.webp",
        landscape_image_url="https://img/landscape.webp",
    )
    without_main = _title_detail(
        title_image_url="",
        portrait_image_url="https://img/portrait.webp",
        landscape_image_url="https://img/landscape.webp",
    )

    assert CoverExporter.resolve_cover_image_url(with_main) == "https://img/portrait.webp"
    assert CoverExporter.resolve_cover_image_url(without_main) == "https://img/portrait.webp"


def test_resolve_cover_image_url_falls_back_to_landscape_then_none() -> None:
    """Verify cover URL resolution uses landscape fallback and returns None when absent."""
    landscape_only = _title_detail(
        title_image_url="",
        portrait_image_url="",
        landscape_image_url="https://img/landscape.webp",
    )
    no_cover = _title_detail(
        title_image_url="",
        portrait_image_url="",
        landscape_image_url="",
    )

    assert CoverExporter.resolve_cover_image_url(landscape_only) == "https://img/landscape.webp"
    assert CoverExporter.resolve_cover_image_url(no_cover) is None


@pytest.mark.parametrize(
    ("cover_format", "expected_pil_format", "expected_mode"),
    [
        ("png", "PNG", "RGBA"),
        ("jpg", "JPEG", "RGB"),
        ("webp", "WEBP", "RGBA"),
    ],
)
def test_dump_title_cover_exports_selected_format(
    tmp_path: Path,
    cover_format: CoverFormat,
    expected_pil_format: str,
    expected_mode: str,
) -> None:
    """Verify cover export downloads bytes and stores the selected image format."""
    image_bytes = BytesIO()
    Image.new("RGBA", (1, 1), (255, 0, 0, 128)).save(image_bytes, format="PNG")
    image_blob = image_bytes.getvalue()

    title_detail = _title_detail(
        title_image_url="https://img/main.webp",
        name="my manga",
        portrait_image_url="",
        landscape_image_url="",
    )
    export_dir = tmp_path / "My Manga"

    CoverExporter.dump_title_cover(
        title_detail,
        export_dir,
        cover_format=cover_format,
        download_image=lambda _url: image_blob,
    )

    cover_path = export_dir / f"cover.{cover_format}"
    assert cover_path.exists()
    with Image.open(cover_path) as image:
        assert image.format == expected_pil_format
        assert image.mode == expected_mode


def test_dump_title_cover_raises_on_invalid_cover_format(
    tmp_path: Path,
) -> None:
    """Verify defensive validation catches unsupported cover formats."""
    image_bytes = BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(image_bytes, format="JPEG")
    image_blob = image_bytes.getvalue()

    title_detail = _title_detail(
        title_image_url="https://img/main.webp",
        name="my manga",
        portrait_image_url="",
        landscape_image_url="",
    )

    with pytest.raises(ValueError, match="Unsupported cover format: bmp"):
        CoverExporter.dump_title_cover(
            title_detail,
            tmp_path / "My Manga",
            cover_format=cast(CoverFormat, "bmp"),
            download_image=lambda _url: image_blob,
        )


def test_dump_title_cover_skips_when_cover_url_is_missing(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify cover export logs and returns when no cover URL is available."""
    title_detail = _title_detail(
        title_image_url="",
        name="my manga",
        portrait_image_url="",
        landscape_image_url="",
    )

    CoverExporter.dump_title_cover(
        title_detail,
        tmp_path / "My Manga",
        cover_format="png",
        download_image=lambda _url: b"",
    )

    assert "Cover export skipped" in caplog.text


def test_dump_title_cover_skips_when_selected_cover_file_already_exists(
    tmp_path: Path,
) -> None:
    """Verify cover export does not re-download when selected cover file exists."""
    title_detail = _title_detail(
        title_image_url="https://img/main.webp",
        name="my manga",
        portrait_image_url="",
        landscape_image_url="",
    )
    export_dir = tmp_path / "My Manga"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "cover.webp").write_bytes(b"already")

    CoverExporter.dump_title_cover(
        title_detail,
        export_dir,
        cover_format="webp",
        download_image=lambda _url: (_ for _ in ()).throw(
            AssertionError("cover should not be downloaded twice")
        ),
    )
