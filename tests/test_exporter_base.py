"""Tests for ExporterBase shared naming and registration behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mloader.constants import Language
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


def _title(name: str = "demo title", language: int = Language.ENGLISH.value) -> SimpleNamespace:
    """Build a minimal title object for exporter-base tests."""
    return SimpleNamespace(name=name, language=language)


def _chapter(name: str = "#1", sub_title: str = "subtitle") -> SimpleNamespace:
    """Build a minimal chapter object for exporter-base tests."""
    return SimpleNamespace(name=name, sub_title=sub_title)


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
    ExporterBase.add_image(None, b"", 0)
    ExporterBase.skip_image(None, 0)
    assert ExporterBase.format.fget(None) is None
