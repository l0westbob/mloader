"""Tests for the current public app surface."""

from __future__ import annotations

import importlib

from mloader.exporters import CBZExporter, ExporterBase, PDFExporter, RawExporter
from mloader.manga_loader.init import MangaLoader


def test_package_and_entrypoint_are_current_public_surface() -> None:
    """Verify package and command-entry imports are part of the current surface."""
    package = importlib.import_module("mloader")
    entrypoint = importlib.import_module("mloader.__main__")

    assert package.__doc__ == "Top-level package for mloader."
    assert callable(entrypoint.main)


def test_runtime_and_exporters_are_current_public_surface() -> None:
    """Verify runtime facade and exporter imports are part of the current surface."""
    assert MangaLoader.__name__ == "MangaLoader"
    assert ExporterBase.__name__ == "ExporterBase"
    assert RawExporter.format == "raw"
    assert CBZExporter.format == "cbz"
    assert PDFExporter.format == "pdf"
