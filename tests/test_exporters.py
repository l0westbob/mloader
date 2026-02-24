"""Tests for concrete exporter implementations."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from mloader.constants import Language
from mloader.exporters.cbz_exporter import CBZExporter
from mloader.exporters.pdf_exporter import PDFExporter
from mloader.exporters.raw_exporter import RawExporter


def _title(
    name: str = "demo title",
    language: int = Language.ENGLISH.value,
    author: str = "author",
) -> SimpleNamespace:
    """Build a minimal title object for exporter tests."""
    return SimpleNamespace(name=name, language=language, author=author)


def _chapter(name: str = "#1", sub_title: str = "start") -> SimpleNamespace:
    """Build a minimal chapter object for exporter tests."""
    return SimpleNamespace(name=name, sub_title=sub_title)


def _jpeg_bytes(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Create a small in-memory JPEG image payload for tests."""
    image = Image.new("RGB", (20, 20), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_raw_exporter_writes_and_skips_existing_image(tmp_path: Path) -> None:
    """Verify raw exporter writes page files and skips existing outputs."""
    exporter = RawExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(b"abc", 0)
    filename = exporter.format_page_name(0)
    path = exporter.path / filename

    assert path.exists()
    assert path.read_bytes() == b"abc"
    assert exporter.skip_image(0) is True


def test_raw_exporter_with_chapter_subdir(tmp_path: Path) -> None:
    """Verify raw exporter can place output in chapter-specific subdirectories."""
    exporter = RawExporter(
        destination=str(tmp_path),
        title=_title(),
        chapter=_chapter(),
        add_chapter_subdir=True,
    )
    assert exporter.path.name == exporter.chapter_name


def test_cbz_exporter_creates_archive_with_images(tmp_path: Path) -> None:
    """Verify CBZ exporter writes image entries into a created archive."""
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(b"img1", 0)
    exporter.add_image(b"img2", 1)
    exporter.close()

    assert exporter.path.exists()

    with zipfile.ZipFile(exporter.path, "r") as archive:
        names = set(archive.namelist())
        comicinfo = archive.read(Path(exporter.chapter_name, "ComicInfo.xml").as_posix()).decode("utf-8")

    assert any(name.endswith(".jpg") for name in names)
    assert "<ComicInfo>" in comicinfo
    assert "<LanguageISO>en</LanguageISO>" in comicinfo


def test_cbz_exporter_comicinfo_escapes_metadata(tmp_path: Path) -> None:
    """Verify ComicInfo.xml escapes special characters from metadata."""
    exporter = CBZExporter(
        destination=str(tmp_path),
        title=_title(name="a & b", author="x < y"),
        chapter=_chapter(name="#7", sub_title='title "quoted"'),
    )

    exporter.add_image(b"img", 0)
    exporter.close()

    with zipfile.ZipFile(exporter.path, "r") as archive:
        comicinfo = archive.read(Path(exporter.chapter_name, "ComicInfo.xml").as_posix()).decode("utf-8")

    assert "<Series>a &amp; b</Series>" in comicinfo
    assert "<Writer>x &lt; y</Writer>" in comicinfo
    assert "<Title>title &quot;quoted&quot;</Title>" in comicinfo


def test_cbz_exporter_comicinfo_write_is_idempotent(tmp_path: Path) -> None:
    """Verify repeated ComicInfo writes do not create duplicate archive entries."""
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(b"img", 0)
    exporter._write_comicinfo_xml_entry()
    exporter._write_comicinfo_xml_entry()
    exporter.close()

    with zipfile.ZipFile(exporter.path, "r") as archive:
        names = archive.namelist()

    assert names.count(Path(exporter.chapter_name, "ComicInfo.xml").as_posix()) == 1


def test_cbz_exporter_skips_when_archive_exists(tmp_path: Path) -> None:
    """Verify CBZ exporter skips writes when destination archive already exists."""
    first = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    first.add_image(b"img1", 0)
    first.close()

    second = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    size_before = second.path.stat().st_size

    second.add_image(b"ignored", 1)
    assert second.skip_image(0) is True
    second.close()

    assert second.path.stat().st_size == size_before


def test_pdf_exporter_writes_pdf(tmp_path: Path) -> None:
    """Verify PDF exporter writes a non-empty PDF output file."""
    exporter = PDFExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(_jpeg_bytes(), 0)
    exporter.close()

    assert exporter.path.exists()
    assert exporter.path.stat().st_size > 0


def test_pdf_exporter_skips_when_pdf_exists(tmp_path: Path) -> None:
    """Verify PDF exporter skips writes when destination PDF already exists."""
    first = PDFExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    first.add_image(_jpeg_bytes(), 0)
    first.close()

    second = PDFExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    size_before = second.path.stat().st_size

    second.add_image(_jpeg_bytes(), 0)
    assert second.skip_image(0) is True
    second.close()

    assert second.path.stat().st_size == size_before


def test_pdf_exporter_close_without_images_is_noop(tmp_path: Path) -> None:
    """Verify closing PDF exporter without images does not create output."""
    exporter = PDFExporter(destination=str(tmp_path), title=_title(name="other"), chapter=_chapter())
    exporter.close()
    assert exporter.path.exists() is False
