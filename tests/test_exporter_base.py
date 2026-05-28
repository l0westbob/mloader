"""Tests for ExporterBase shared naming and registration behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mloader.constants import Language
from mloader.domain.manga import Chapter, Title
from mloader.exporters.exporter_base import ExporterBase, _is_extra


class DummyExporter(ExporterBase):
    """Minimal exporter implementation used for ExporterBase tests."""

    format = "dummy"

    def add_image(self, image_data: bytes, index: int | range) -> None:
        """Store the latest add_image call payload for assertions."""
        self.last = (image_data, index)

    def skip_image(self, index: int | range) -> bool:
        """Never skip any images in this test exporter."""
        del index
        return False


def _title(
    name: str = "demo title",
    language: int = Language.ENGLISH.value,
    author: str = "author",
) -> SimpleNamespace:
    """Build a minimal title object for exporter-base tests."""
    return SimpleNamespace(
        name=name,
        language=language,
        author=author,
        portrait_image_url="",
        landscape_image_url="",
    )


def _chapter(name: str = "#1", sub_title: str = "subtitle") -> SimpleNamespace:
    """Build a minimal chapter object for exporter-base tests."""
    return SimpleNamespace(chapter_id=1, name=name, sub_title=sub_title, thumbnail_url="")


def test_is_extra_detection() -> None:
    """Verify extra chapter detection for Ex and numeric chapters."""
    assert _is_extra("#Ex") is True
    assert _is_extra("#1") is False


def test_exporter_base_formats_prefix_suffix_and_page_names(tmp_path: Path) -> None:
    """Verify exporter base derives expected prefixes, suffixes, and page names."""
    exporter = DummyExporter(
        destination=str(tmp_path),
        title=_title(language=Language.FRENCH.value),
        chapter=_chapter(name="#12", sub_title=""),
    )

    assert "[FRENCH]" in exporter._chapter_prefix
    assert exporter._chapter_suffix == "- Unknown"
    assert exporter.format_page_name(2) == f"{exporter._chapter_prefix} - p002 - Unknown.jpg"
    assert exporter.format_page_name(range(1, 4), ext="png").endswith(".png")


@pytest.mark.parametrize(
    ("title", "chapter", "page", "expected_name"),
    [
        (
            _title(name="demo title", language=Language.ENGLISH.value),
            _chapter(name="#12", sub_title="A/B: C?"),
            2,
            "Demo Title - 12 - p002 - A B C.jpg",
        ),
        (
            _title(name="demo title", language=Language.FRENCH.value),
            _chapter(name="#12", sub_title=""),
            2,
            "Demo Title [FRENCH] - 12 - p002 - Unknown.jpg",
        ),
        (
            _title(name="demo title", language=Language.ENGLISH.value),
            _chapter(name="#7", sub_title="Double Page"),
            range(10, 12),
            "Demo Title - 7 - p010-012 - Double Page.jpg",
        ),
        (
            _title(name="demo title", language=Language.ENGLISH.value),
            _chapter(name="#Ex", sub_title="Bonus"),
            1,
            "Demo Title - Ex - p001 - Bonus.jpg",
        ),
        (
            _title(name="demo title", language=Language.ENGLISH.value),
            _chapter(name="One Shot Special", sub_title=""),
            1,
            "Demo Title - One Shot Special - p001 - Unknown.jpg",
        ),
    ],
)
def test_exporter_base_golden_page_names(
    tmp_path: Path,
    title: SimpleNamespace,
    chapter: SimpleNamespace,
    page: int | range,
    expected_name: str,
) -> None:
    """Verify golden filename behavior for languages, extras, one-shots, and ranges."""
    exporter = DummyExporter(destination=str(tmp_path), title=title, chapter=chapter)

    assert exporter.format_page_name(page) == expected_name
    assert exporter.is_extra is _is_extra(chapter.name)
    if chapter.name == "One Shot Special":
        assert exporter.is_oneshot is True


def test_exporter_base_accepts_domain_title_and_chapter_dtos(tmp_path: Path) -> None:
    """Verify shared exporter naming only depends on the stable domain DTO shape."""
    exporter = DummyExporter(
        destination=str(tmp_path),
        title=Title(
            title_id=100494,
            name="domain title",
            author="Domain Author",
            portrait_image_url="https://example.invalid/portrait.webp",
            landscape_image_url="https://example.invalid/landscape.webp",
            language=Language.ENGLISH.value,
        ),
        chapter=Chapter(
            title_id=100494,
            chapter_id=1024974,
            name="#001",
            sub_title="Domain Chapter",
            thumbnail_url="https://example.invalid/chapter.webp",
        ),
    )

    assert exporter.format_page_name(1) == "Domain Title - 001 - p001 - Domain Chapter.jpg"


def test_exporter_base_handles_alternate_vietnamese_language_code(tmp_path: Path) -> None:
    """Verify alternate Vietnamese code still produces a stable language prefix."""
    exporter = DummyExporter(
        destination=str(tmp_path),
        title=_title(language=8),
        chapter=_chapter(),
    )

    assert "[VIETNAMESE]" in exporter._chapter_prefix


def test_exporter_base_handles_unknown_language_code(tmp_path: Path) -> None:
    """Verify unknown language codes do not raise and keep a readable tag."""
    exporter = DummyExporter(
        destination=str(tmp_path),
        title=_title(language=99),
        chapter=_chapter(),
    )

    assert "[LANG-99]" in exporter._chapter_prefix


def test_exporter_base_iso_language_maps_known_code(tmp_path: Path) -> None:
    """Verify known internal language codes map to expected ISO values."""
    exporter = DummyExporter(
        destination=str(tmp_path),
        title=_title(language=Language.SPANISH.value),
        chapter=_chapter(),
    )

    assert exporter._iso_language() == "es"


def test_exporter_base_iso_language_falls_back_to_english(tmp_path: Path) -> None:
    """Verify unknown language codes default to English ISO code."""
    exporter = DummyExporter(
        destination=str(tmp_path),
        title=_title(language=99),
        chapter=_chapter(),
    )

    assert exporter._iso_language() == "en"


def test_exporter_base_windows_path_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify Windows mode adds extended-length prefix to destination paths."""
    monkeypatch.setattr("mloader.exporters.exporter_base.is_windows", lambda: True)

    exporter = DummyExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    assert exporter.destination.startswith("\\\\?\\")


def test_exporter_base_registers_subclasses_and_close_pass(tmp_path: Path) -> None:
    """Verify subclasses register format keys and default close is callable."""
    exporter = DummyExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    exporter.close()

    assert ExporterBase.FORMAT_REGISTRY["dummy"] is DummyExporter


def test_abstract_base_methods_have_noop_defaults() -> None:
    """Verify abstract base placeholders are callable for coverage purposes."""
    exporter = DummyExporter(destination="/tmp", title=_title(), chapter=_chapter())
    ExporterBase.add_image(exporter, b"", 0)
    ExporterBase.skip_image(exporter, 0)


def test_exporter_base_requires_non_empty_format() -> None:
    """Verify subclass registration rejects missing/empty format keys."""
    with pytest.raises(TypeError):

        class _InvalidExporter(ExporterBase):
            format = ""

            def add_image(self, image_data: bytes, index: int | range) -> None:
                del image_data, index

            def skip_image(self, index: int | range) -> bool:
                del index
                return False
