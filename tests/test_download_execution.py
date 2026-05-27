"""Tests for concrete download execution behavior."""

from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

import click
import pytest
from PIL import Image

from mloader.constants import PageType
from mloader.domain.planning import DownloadPlan, TitleDownloadPlan
from mloader.domain.requests import DownloadSummary
from mloader.errors import DownloadInterruptedError
from mloader.manga_loader.chapter_planning import ChapterMetadata
from mloader.manga_loader.run_report import RunReport
from tests.downloader_helpers import (
    dummy_downloader,
    DummyResponse,
    full_downloader,
    download_plan as _download_plan,
    manga_page as _manga_page,
    run_report as _run_report,
    title_detail as _title_detail,
    title_plan as _title_plan,
)


def test_download_calls_prepare_and_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify download() delegates to planning and plan execution."""
    calls: dict[str, Any] = {}

    def _prepare_download_plan(*args: Any) -> DownloadPlan:
        """Capture prepare args and return a sentinel plan."""
        calls["prepare"] = args
        return _download_plan(_title_plan(title_id=42, chapter_ids={1}))

    def _download(download_plan: DownloadPlan, report: RunReport) -> None:
        """Capture the plan forwarded to _download."""
        del report
        calls["download"] = download_plan

    loader = dummy_downloader()
    monkeypatch.setattr(loader, "_prepare_download_plan", _prepare_download_plan)
    monkeypatch.setattr(loader, "_download", _download)
    summary = loader.download(
        title_ids={100312},
        chapter_numbers=None,
        chapter_ids={1024959},
        min_chapter=1,
        max_chapter=5,
        last_chapter=True,
    )

    assert calls["prepare"] == ({100312}, None, {1024959}, 1, 5, True)
    assert calls["download"].selections[0].title_id == 42
    assert calls["download"].selections[0].chapter_ids == frozenset({1})
    assert summary == DownloadSummary(
        downloaded=0,
        skipped_manifest=0,
        failed=0,
        failed_chapter_ids=(),
    )


def test_download_clears_run_cache_before_and_after_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify download lifecycle clears run-level API cache at start and end."""
    calls: list[str] = []

    def _prepare_download_plan(*args: Any) -> DownloadPlan:
        """Return empty plan to keep flow deterministic."""
        del args
        return DownloadPlan(title_plans=())

    def _download(download_plan: DownloadPlan, report: RunReport) -> None:
        """Record download invocation payload."""
        del download_plan, report
        calls.append("download")

    def _clear_api_caches_for_run() -> None:
        """Record run-cache clearing hook invocation."""
        calls.append("clear_run")

    loader = dummy_downloader()
    monkeypatch.setattr(loader, "_prepare_download_plan", _prepare_download_plan)
    monkeypatch.setattr(loader, "_download", _download)
    monkeypatch.setattr(loader, "_clear_api_caches_for_run", _clear_api_caches_for_run)
    loader.download(
        title_ids={100312},
        chapter_numbers=None,
        chapter_ids=None,
        min_chapter=0,
        max_chapter=10,
    )

    assert calls == ["clear_run", "download", "clear_run"]


def test_download_raises_interrupted_error_with_partial_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify interrupted runs raise partial-summary wrapper error."""

    def _prepare_download_plan(*args: Any) -> DownloadPlan:
        """Return deterministic download plan."""
        del args
        return _download_plan(_title_plan(title_id=42, chapter_ids={1}))

    def _download(download_plan: DownloadPlan, report: RunReport) -> None:
        """Mark counters, then emulate user interrupt."""
        del download_plan
        report.mark_downloaded()
        report.mark_manifest_skipped(2)
        report.mark_failed(99)
        raise KeyboardInterrupt

    loader = dummy_downloader()
    monkeypatch.setattr(loader, "_prepare_download_plan", _prepare_download_plan)
    monkeypatch.setattr(loader, "_download", _download)

    with pytest.raises(DownloadInterruptedError) as interrupted:
        loader.download(
            title_ids={100312},
            chapter_numbers=None,
            chapter_ids=None,
            min_chapter=0,
            max_chapter=10,
        )

    assert interrupted.value.summary == DownloadSummary(
        downloaded=1,
        skipped_manifest=2,
        failed=1,
        failed_chapter_ids=(99,),
    )


def test_download_iterates_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _download iterates titles in insertion order with indexes."""
    calls: list[tuple[int, int, int, frozenset[int]]] = []

    def _process_title(
        title_index: int,
        total_titles: int,
        title_plan: TitleDownloadPlan,
        *,
        report: RunReport,
    ) -> None:
        """Record _process_title invocation payloads."""
        del report
        calls.append((title_index, total_titles, title_plan.title_id, title_plan.chapter_ids))

    loader = dummy_downloader()
    monkeypatch.setattr(loader, "_process_title", _process_title)
    loader._download(
        DownloadPlan(
            title_plans=(
                _title_plan(title_id=10, chapter_ids={1, 2}),
                _title_plan(title_id=20, chapter_ids={3}),
            )
        ),
        report=_run_report(),
    )

    assert calls == [(1, 2, 10, frozenset({1, 2})), (2, 2, 20, frozenset({3}))]


def test_execution_service_processes_pages_through_page_image_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify execution page export delegates plain and encrypted images to image service."""

    @contextmanager
    def fake_progressbar(items: list[Any], **kwargs: Any) -> Any:
        del kwargs
        yield items

    class Exporter:
        def __init__(self) -> None:
            self.images: list[bytes] = []

        def skip_image(self, index: int | range) -> bool:
            del index
            return False

        def add_image(self, image_data: bytes, index: int | range) -> None:
            del index
            self.images.append(image_data)

        def close(self) -> None:
            """Accept exporter finalization without side effects."""

    monkeypatch.setattr(click, "progressbar", fake_progressbar)
    exporter = Exporter()
    loader = dummy_downloader()

    loader._process_chapter_pages(
        [
            _manga_page("plain", page_type=PageType.SINGLE),
            _manga_page("encrypted", page_type=PageType.SINGLE, encryption_key="abcd"),
        ],
        chapter_name="#1",
        exporter=exporter,
    )

    assert exporter.images == [b"img:plain", b"dec:encrypted:abcd"]


def test_execution_service_dumps_title_metadata_and_cover(tmp_path: Path) -> None:
    """Verify execution service wires metadata and cover exporters with configured transport."""
    image_bytes = BytesIO()
    Image.new("RGBA", (1, 1), (255, 0, 0, 128)).save(image_bytes, format="PNG")
    loader = full_downloader(
        destination=str(tmp_path),
        cover_format="webp",
        response=DummyResponse(content=image_bytes.getvalue()),
    )
    title_detail = _title_detail(
        title_image_url="https://img/main.webp",
        name="Title",
        chapters=[],
    )

    loader._dump_title_metadata(
        title_detail,
        {1: ChapterMetadata(thumbnail_url="", chapter_id=1, sub_title="Sub")},
        tmp_path,
    )
    loader._dump_title_cover(title_detail, tmp_path)

    assert (tmp_path / "title_metadata.json").exists()
    assert (tmp_path / "cover.webp").exists()
