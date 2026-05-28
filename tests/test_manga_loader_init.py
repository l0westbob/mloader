"""Tests for MangaLoader initialization behavior."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from requests import Session

from mloader.domain.manga import Chapter, ChapterGroup, Title, TitleDetail
from mloader.infrastructure.mangaplus.transport import configure_transport
from mloader.manga_loader.init import MangaLoader
from mloader.manga_loader.runner import DownloadRunner
from mloader.types import SessionLike
from tests.downloader_helpers import NullExporterFactory


EXPORTER_FACTORY = NullExporterFactory("mloader_downloads")


def _title_detail() -> TitleDetail:
    """Build a minimal title detail for runtime planning tests."""
    chapter = Chapter(
        title_id=100001,
        chapter_id=200001,
        name="#001",
        sub_title="A Beginning",
        thumbnail_url="https://example.test/chapter.webp",
    )
    return TitleDetail(
        title=Title(
            title_id=100001,
            name="Demo",
            author="Author",
            portrait_image_url="https://example.test/portrait.webp",
            landscape_image_url="https://example.test/landscape.webp",
            language=0,
        ),
        title_image_url="https://example.test/title.webp",
        overview="Overview",
        non_appearance_info="",
        number_of_views=1,
        chapter_groups=(
            ChapterGroup(first_chapters=(chapter,), mid_chapters=(), last_chapters=()),
        ),
    )


def test_manga_loader_creates_independent_default_sessions() -> None:
    """Ensure separate MangaLoader instances do not share default sessions."""
    loader_a = MangaLoader(exporter=EXPORTER_FACTORY, quality="high", split=False, meta=False)
    loader_b = MangaLoader(exporter=EXPORTER_FACTORY, quality="high", split=False, meta=False)

    assert loader_a.session is not loader_b.session
    assert loader_a.session.headers["User-Agent"] == "okhttp/4.12.0"
    assert "Host" not in loader_a.session.headers


def test_manga_loader_configures_transport_defaults() -> None:
    """Ensure loader sets destination, format, and timeout defaults."""
    session = Session()
    loader = MangaLoader(
        exporter=EXPORTER_FACTORY,
        quality="high",
        split=False,
        meta=False,
        session=cast(SessionLike, session),
    )

    assert loader.destination == "mloader_downloads"
    assert loader.output_format == "cbz"
    assert loader.request_timeout == (5.0, 30.0)
    assert session.get_adapter("https://").max_retries.total == 3
    assert loader._runtime.resume is True
    assert loader._runtime.manifest_reset is False
    assert loader._runtime.cover_format == "png"


def test_runtime_uses_concrete_runner() -> None:
    """Ensure the live runtime uses the canonical concrete runner."""
    loader = MangaLoader(exporter=EXPORTER_FACTORY, quality="high", split=False, meta=False)

    assert type(loader._runtime) is DownloadRunner


def test_runtime_prepares_domain_download_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the runtime resolves filters through its concrete planning hook."""
    loader = MangaLoader(exporter=EXPORTER_FACTORY, quality="high", split=False, meta=False)

    monkeypatch.setattr(loader._runtime, "_get_title_details", lambda _title_id: _title_detail())

    plan = loader._runtime._prepare_download_plan(
        title_ids={100001},
        chapter_numbers=None,
        chapter_ids=None,
        min_chapter=0,
        max_chapter=10,
        last_chapter=False,
    )

    assert plan.title_count == 1
    assert plan.title_plans[0].chapter_ids == frozenset({200001})


def test_manga_loader_enables_payload_capture_when_directory_is_set(tmp_path: Path) -> None:
    """Ensure loader initializes payload capture helper when configured."""
    loader = MangaLoader(
        exporter=EXPORTER_FACTORY,
        quality="high",
        split=False,
        meta=False,
        capture_api_dir=str(tmp_path / "captures"),
    )

    assert loader.payload_capture is not None


def test_runtime_transport_helper_configures_retries() -> None:
    """Ensure runtime transport helper configures retries."""
    session = Session()

    configure_transport(cast(SessionLike, session), retries=4)

    assert session.get_adapter("https://").max_retries.total == 4


def test_manga_loader_download_delegates_to_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure facade download method forwards parameters to composed runtime object."""
    loader = MangaLoader(exporter=EXPORTER_FACTORY, quality="high", split=False, meta=False)
    observed: dict[str, object] = {}

    def _download(**kwargs: object) -> None:
        observed.update(kwargs)

    monkeypatch.setattr(loader._runtime, "download", _download)

    loader.download(
        title_ids={100312},
        chapter_ids={1024959},
        min_chapter=3,
        max_chapter=4,
        last_chapter=True,
    )

    assert observed == {
        "title_ids": {100312},
        "chapter_numbers": None,
        "chapter_ids": {1024959},
        "min_chapter": 3,
        "max_chapter": 4,
        "last_chapter": True,
    }


def test_manga_loader_unknown_attribute_raises_attribute_error() -> None:
    """Ensure facade exposes only explicit API and rejects unknown attributes."""
    loader = MangaLoader(exporter=EXPORTER_FACTORY, quality="high", split=False, meta=False)

    with pytest.raises(AttributeError):
        getattr(loader, "runtime_marker")
