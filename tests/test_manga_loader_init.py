"""Tests for MangaLoader initialization behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
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
    assert loader._runtime.resume is True
    assert loader._runtime.manifest_reset is False


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


def test_manga_loader_static_transport_proxy_configures_retries() -> None:
    """Ensure facade transport helper delegates to runtime transport configuration."""
    session = Session()

    MangaLoader._configure_transport(session, retries=4)

    assert session.get_adapter("https://").max_retries.total == 4


def test_manga_loader_download_delegates_to_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure facade download method forwards parameters to composed runtime object."""
    loader = MangaLoader(exporter=None, quality="high", split=False, meta=False)
    observed: dict[str, object] = {}

    def _download(**kwargs: object) -> None:
        observed.update(kwargs)

    monkeypatch.setattr(loader._runtime, "download", _download)

    loader.download(
        title_ids={100312},
        chapter_ids={102277},
        min_chapter=3,
        max_chapter=4,
        last_chapter=True,
    )

    assert observed == {
        "title_ids": {100312},
        "chapter_ids": {102277},
        "min_chapter": 3,
        "max_chapter": 4,
        "last_chapter": True,
    }


def test_manga_loader_unknown_attribute_raises_attribute_error() -> None:
    """Ensure facade exposes only explicit API and rejects unknown attributes."""
    loader = MangaLoader(exporter=None, quality="high", split=False, meta=False)

    with pytest.raises(AttributeError):
        _ = loader.runtime_marker
