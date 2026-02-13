import io
import zipfile
from types import SimpleNamespace

from PIL import Image

from mloader.constants import Language
from mloader.exporters.cbz_exporter import CBZExporter
from mloader.exporters.pdf_exporter import PDFExporter
from mloader.exporters.raw_exporter import RawExporter


def _title(name="demo title", language=Language.ENGLISH.value):
    return SimpleNamespace(name=name, language=language)


def _chapter(name="#1", sub_title="start"):
    return SimpleNamespace(name=name, sub_title=sub_title)


def _jpeg_bytes(color=(255, 0, 0)):
    image = Image.new("RGB", (20, 20), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_raw_exporter_writes_and_skips_existing_image(tmp_path):
    exporter = RawExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(b"abc", 0)
    filename = exporter.format_page_name(0)
    path = exporter.path / filename

    assert path.exists()
    assert path.read_bytes() == b"abc"
    assert exporter.skip_image(0) is True


def test_raw_exporter_with_chapter_subdir(tmp_path):
    exporter = RawExporter(
        destination=str(tmp_path),
        title=_title(),
        chapter=_chapter(),
        add_chapter_subdir=True,
    )
    assert exporter.path.name == exporter.chapter_name


def test_cbz_exporter_creates_archive_with_images(tmp_path):
    exporter = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(b"img1", 0)
    exporter.add_image(b"img2", 1)
    exporter.close()

    assert exporter.path.exists()

    with zipfile.ZipFile(exporter.path, "r") as archive:
        names = set(archive.namelist())

    assert any(name.endswith(".jpg") for name in names)


def test_cbz_exporter_skips_when_archive_exists(tmp_path):
    first = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    first.add_image(b"img1", 0)
    first.close()

    second = CBZExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    size_before = second.path.stat().st_size

    second.add_image(b"ignored", 1)
    assert second.skip_image(0) is True
    second.close()

    assert second.path.stat().st_size == size_before


def test_pdf_exporter_writes_pdf(tmp_path):
    exporter = PDFExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    exporter.add_image(_jpeg_bytes(), 0)
    exporter.close()

    assert exporter.path.exists()
    assert exporter.path.stat().st_size > 0


def test_pdf_exporter_skips_when_pdf_exists(tmp_path):
    first = PDFExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    first.add_image(_jpeg_bytes(), 0)
    first.close()

    second = PDFExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    size_before = second.path.stat().st_size

    second.add_image(_jpeg_bytes(), 0)
    assert second.skip_image(0) is True
    second.close()

    assert second.path.stat().st_size == size_before


def test_pdf_exporter_close_without_images_is_noop(tmp_path):
    exporter = PDFExporter(destination=str(tmp_path), title=_title(name="other"), chapter=_chapter())
    exporter.close()
    assert exporter.path.exists() is False
