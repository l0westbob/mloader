"""Tests for concrete exporter implementations."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from mloader.constants import Language
from mloader.domain.manga import Chapter, Title, TitleTag
from mloader.exporters.cbz_exporter import CBZExporter
from mloader.exporters.pdf_exporter import PDFExporter
from mloader.exporters.raw_exporter import RawExporter


def _title(
    name: str = "demo title",
    language: int = Language.ENGLISH.value,
    author: str = "author",
    overview: str = "",
    tags: tuple[TitleTag, ...] = (),
    web_url: str = "",
) -> SimpleNamespace:
    """Build a minimal title object for exporter tests."""
    return SimpleNamespace(
        name=name,
        language=language,
        author=author,
        overview=overview,
        tags=tags,
        web_url=web_url,
    )


def _chapter(name: str = "#1", sub_title: str = "start", start_timestamp: int = 0) -> SimpleNamespace:
    """Build a minimal chapter object for exporter tests."""
    return SimpleNamespace(name=name, sub_title=sub_title, start_timestamp=start_timestamp)


def _domain_title() -> Title:
    """Build a stable domain title DTO for exporter contract tests."""
    return Title(
        title_id=100494,
        name="domain title",
        author="Domain Author",
        portrait_image_url="https://example.invalid/portrait.webp",
        landscape_image_url="https://example.invalid/landscape.webp",
        language=Language.ENGLISH.value,
    )


def _domain_chapter() -> Chapter:
    """Build a stable domain chapter DTO for exporter contract tests."""
    return Chapter(
        title_id=100494,
        chapter_id=1024974,
        name="#001",
        sub_title="Domain Chapter",
        thumbnail_url="https://example.invalid/chapter.webp",
    )


def _jpeg_bytes(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Create a small in-memory JPEG image payload for tests."""
    image = Image.new("RGB", (20, 20), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _png_rgba_bytes() -> bytes:
    """Create a small RGBA PNG payload for PDF conversion branch tests."""
    image = Image.new("RGBA", (20, 20), color=(255, 0, 0, 120))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
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


def test_concrete_exporters_accept_domain_dtos(tmp_path: Path) -> None:
    """Verify exporters write outputs from stable domain DTOs, not protobuf instances."""
    title = _domain_title()
    chapter = _domain_chapter()

    raw = RawExporter(destination=str(tmp_path), title=title, chapter=chapter)
    raw.add_image(b"raw", 1)
    assert (raw.path / raw.format_page_name(1)).read_bytes() == b"raw"

    cbz = CBZExporter(destination=str(tmp_path), title=title, chapter=chapter)
    cbz.add_image(b"cbz", 1)
    cbz.close()
    assert cbz.path.name == "Domain Title - 001 - Domain Chapter.cbz"
    assert cbz.path.exists()

    pdf = PDFExporter(destination=str(tmp_path), title=title, chapter=chapter)
    pdf.add_image(_jpeg_bytes(), 1)
    pdf.close()
    assert pdf.path.name == "Domain Title - 001 - Domain Chapter.pdf"
    assert pdf.path.exists()


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
        comicinfo = archive.read("ComicInfo.xml").decode("utf-8")

    assert names == {
        exporter.format_page_name(0),
        exporter.format_page_name(1),
        "ComicInfo.xml",
    }
    assert all("/" not in name for name in names)
    assert "<ComicInfo>" in comicinfo
    assert "<LanguageISO>en</LanguageISO>" in comicinfo
    assert "<PageCount>2</PageCount>" in comicinfo
    assert "<Format>Digital</Format>" in comicinfo


def test_cbz_exporter_comicinfo_escapes_metadata(tmp_path: Path) -> None:
    """Verify ComicInfo.xml escapes special characters from metadata."""
    exporter = CBZExporter(
        destination=str(tmp_path),
        title=_title(
            name="a & b",
            author="x < y",
            overview="summary <quoted> & strong",
            tags=(TitleTag(name="Action & Adventure", slug="action"),),
            web_url="https://example.invalid/a?b=1&c=2",
        ),
        chapter=_chapter(name="#7", sub_title='title "quoted"', start_timestamp=1747407600),
    )

    exporter.add_image(b"img", 0)
    exporter.close()

    with zipfile.ZipFile(exporter.path, "r") as archive:
        comicinfo = archive.read("ComicInfo.xml").decode("utf-8")

    assert "<Series>a &amp; b</Series>" in comicinfo
    assert "<Writer>x &lt; y</Writer>" in comicinfo
    assert "<Title>title &quot;quoted&quot;</Title>" in comicinfo
    assert "<Summary>summary &lt;quoted&gt; &amp; strong</Summary>" in comicinfo
    assert "<Genre>Action &amp; Adventure</Genre>" in comicinfo
    assert "<Tags>Action &amp; Adventure</Tags>" in comicinfo
    assert "<Web>https://example.invalid/a?b=1&amp;c=2</Web>" in comicinfo
    assert "<Year>2025</Year>" in comicinfo
    assert "<Month>5</Month>" in comicinfo
    assert "<Day>16</Day>" in comicinfo


def test_cbz_exporter_omits_missing_optional_comicinfo_metadata(tmp_path: Path) -> None:
    """Verify empty MangaPlus metadata does not produce empty ComicInfo elements."""
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(b"img", 0)
    exporter.close()

    with zipfile.ZipFile(exporter.path, "r") as archive:
        comicinfo = archive.read("ComicInfo.xml").decode("utf-8")

    assert "<Summary>" not in comicinfo
    assert "<Tags>" not in comicinfo
    assert "<Web>" not in comicinfo
    assert "<Year>" not in comicinfo
    assert "<Month>" not in comicinfo
    assert "<Day>" not in comicinfo
    assert "<Genre>Manga</Genre>" in comicinfo


def test_cbz_exporter_comicinfo_write_is_idempotent(tmp_path: Path) -> None:
    """Verify repeated ComicInfo writes do not create duplicate archive entries."""
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(b"img", 0)
    exporter._write_comicinfo_xml_entry()
    exporter._write_comicinfo_xml_entry()
    exporter.close()

    with zipfile.ZipFile(exporter.path, "r") as archive:
        names = archive.namelist()

    assert names.count("ComicInfo.xml") == 1


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


def test_cbz_exporter_cleans_temp_archive_when_close_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify failed CBZ finalization does not leave a corrupt final archive."""
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    exporter.add_image(b"img", 0)
    temp_path = exporter._temp_path

    def _raise_comicinfo_error() -> None:
        raise RuntimeError("comicinfo failed")

    monkeypatch.setattr(exporter, "_write_comicinfo_xml_entry", _raise_comicinfo_error)

    with pytest.raises(RuntimeError, match="comicinfo failed"):
        exporter.close()

    assert exporter.path.exists() is False
    assert temp_path is not None
    assert temp_path.exists() is False


def test_cbz_exporter_close_handles_missing_temp_path(tmp_path: Path) -> None:
    """Verify defensive CBZ close path exits when temp path state is missing."""
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    exporter.add_image(b"img", 0)
    temp_path = exporter._temp_path
    exporter._temp_path = None

    exporter.close()

    assert exporter.path.exists() is False
    assert temp_path is not None
    temp_path.unlink(missing_ok=True)


def test_cbz_exporter_discard_removes_temp_archive(tmp_path: Path) -> None:
    """Verify CBZ discard cleans partial archives before close."""
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    exporter.add_image(b"img", 0)
    temp_path = exporter._temp_path

    exporter.discard()

    assert exporter.path.exists() is False
    assert temp_path is not None
    assert temp_path.exists() is False


def test_cbz_exporter_discard_noops_when_output_exists(tmp_path: Path) -> None:
    """Verify discard respects existing archive skip mode."""
    first = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    first.add_image(b"img", 0)
    first.close()

    second = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    second.discard()

    assert second.path.exists() is True


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
    exporter = PDFExporter(
        destination=str(tmp_path), title=_title(name="other"), chapter=_chapter()
    )
    exporter.close()
    assert exporter.path.exists() is False


def test_pdf_exporter_cleans_temp_page_buffers_after_close(tmp_path: Path) -> None:
    """Verify PDF exporter releases temporary buffering state once closed."""
    exporter = PDFExporter(
        destination=str(tmp_path), title=_title(name="buffers"), chapter=_chapter()
    )

    exporter.add_image(_jpeg_bytes(), 5)
    exporter.add_image(_jpeg_bytes(color=(0, 255, 0)), 1)
    exporter.close()

    assert exporter.path.exists() is True
    assert exporter._temp_dir is None
    assert exporter._page_paths == []


def test_pdf_exporter_add_image_noops_when_temp_dir_is_missing(tmp_path: Path) -> None:
    """Verify add_image exits cleanly when temp buffering is unexpectedly unavailable."""
    exporter = PDFExporter(
        destination=str(tmp_path), title=_title(name="no-temp"), chapter=_chapter()
    )
    exporter._temp_dir = None
    exporter.close()

    exporter.add_image(_jpeg_bytes(), 0)

    assert exporter._page_paths == []


def test_pdf_exporter_build_inputs_without_temp_dir_returns_empty(tmp_path: Path) -> None:
    """Verify defensive PDF input builder handles missing temp state."""
    exporter = PDFExporter(
        destination=str(tmp_path), title=_title(name="no-inputs"), chapter=_chapter()
    )
    exporter._temp_dir = None

    assert exporter._build_pdf_inputs() == []


def test_pdf_exporter_close_without_pdf_inputs_is_noop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify close exits cleanly when no prepared PDF inputs remain."""
    exporter = PDFExporter(
        destination=str(tmp_path), title=_title(name="empty-inputs"), chapter=_chapter()
    )
    exporter.add_image(_jpeg_bytes(), 0)
    monkeypatch.setattr(exporter, "_build_pdf_inputs", lambda: [])

    exporter.close()

    assert exporter.path.exists() is False


def test_pdf_exporter_handles_rgba_images_and_range_index(tmp_path: Path) -> None:
    """Verify PDF exporter converts RGBA pages and accepts range-based page indexes."""
    exporter = PDFExporter(destination=str(tmp_path), title=_title(name="rgba"), chapter=_chapter())

    exporter.add_image(_png_rgba_bytes(), range(1, 2))
    exporter.close()

    assert exporter.path.exists() is True
    assert exporter.path.stat().st_size > 0


def test_pdf_exporter_cleans_temp_files_when_conversion_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify failed PDF conversion leaves no final corrupt artifact."""
    exporter = PDFExporter(destination=str(tmp_path), title=_title(name="fail"), chapter=_chapter())
    exporter.add_image(_jpeg_bytes(), 0)
    temp_dir = exporter._temp_dir

    def _raise_convert(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("convert failed")

    monkeypatch.setattr("mloader.exporters.pdf_exporter.img2pdf.convert", _raise_convert)

    with pytest.raises(RuntimeError, match="convert failed"):
        exporter.close()

    assert exporter.path.exists() is False
    assert exporter._temp_dir is None
    assert exporter._page_paths == []
    assert temp_dir is not None
    assert Path(temp_dir.name).exists() is False


def test_pdf_exporter_discard_removes_buffered_pages(tmp_path: Path) -> None:
    """Verify PDF discard cleans page buffers before close."""
    exporter = PDFExporter(
        destination=str(tmp_path), title=_title(name="discard"), chapter=_chapter()
    )
    exporter.add_image(_jpeg_bytes(), 0)
    temp_dir = exporter._temp_dir

    exporter.discard()

    assert exporter.path.exists() is False
    assert exporter._temp_dir is None
    assert exporter._page_paths == []
    assert temp_dir is not None
    assert Path(temp_dir.name).exists() is False
