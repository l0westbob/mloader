"""Tests for MangaLoader initialization behavior."""

from __future__ import annotations

from pathlib import Path

from requests import Session

from mloader.manga_loader.init import MangaLoader


def test_manga_loader_creates_independent_default_sessions() -> None:
    """Ensure separate MangaLoader instances do not share default sessions."""
    loader_a = MangaLoader(exporter=None, quality="high", split=False, meta=False)
    loader_b = MangaLoader(exporter=None, quality="high", split=False, meta=False)

    assert loader_a.session is not loader_b.session
    assert "User-Agent" in loader_a.session.headers


def test_manga_loader_configures_transport_defaults() -> None:
    """Ensure loader sets destination, format, and timeout defaults."""
    session = Session()
    loader = MangaLoader(
        exporter=None,
        quality="high",
        split=False,
        meta=False,
        session=session,
    )

    assert loader.destination == "mloader_downloads"
    assert loader.output_format == "cbz"
    assert loader.request_timeout == (5.0, 30.0)
    assert session.get_adapter("https://").max_retries.total == 3


def test_manga_loader_enables_payload_capture_when_directory_is_set(tmp_path: Path) -> None:
    """Ensure loader initializes payload capture helper when configured."""
    loader = MangaLoader(
        exporter=None,
        quality="high",
        split=False,
        meta=False,
        capture_api_dir=str(tmp_path / "captures"),
    )

    assert loader.payload_capture is not None
