"""Tests for download orchestration helpers."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import click
import pytest

from mloader.constants import PageType
from mloader.domain.requests import DownloadSummary
from mloader.errors import SubscriptionRequiredError
from mloader.manga_loader.downloader import DownloadInterruptedError, DownloadMixin
from mloader.manga_loader.run_report import RunReport
from mloader.manga_loader.services import ChapterMetadata


class DummyDownloader(DownloadMixin):
    """DownloadMixin harness overriding selected side-effect methods."""

    def __init__(self, destination: str = "/tmp/out") -> None:
        """Initialize downloader with a fake exporter destination."""
        self.exporter = SimpleNamespace(keywords={"destination": destination})
        self.destination = destination
        self.output_format = "pdf"
        self.request_timeout = (0.1, 0.1)
        self.meta = False
        self.resume = True
        self.manifest_reset = False

    def _extract_chapter_data(self, title_dump: Any) -> dict[int, dict[str, Any]]:
        """Return pre-seeded chapter data stored on ``title_dump``."""
        return title_dump.chapter_data

    def _download_image(self, url: str) -> bytes:
        """Return deterministic bytes for a given image URL."""
        return f"img:{url}".encode("utf-8")

    def _decrypt_image(self, url: str, encryption_hex: str) -> bytearray:
        """Return deterministic decrypted bytes for encrypted page URLs."""
        return bytearray(f"dec:{url}:{encryption_hex}".encode("utf-8"))


class FullDownloader(DownloadMixin):
    """DownloadMixin harness using real mixin internals where possible."""

    def __init__(self, destination: str = "/tmp/out") -> None:
        """Initialize downloader with a fake exporter destination and session."""
        self.exporter = SimpleNamespace(keywords={"destination": destination})
        self.destination = destination
        self.output_format = "pdf"
        self.request_timeout = (0.1, 0.1)
        self.meta = False
        self.resume = True
        self.manifest_reset = False
        self.session = DummySession(DummyResponse(content=b"default"))


class DummyResponse:
    """Simple HTTP response test double with status tracking."""

    def __init__(self, content: bytes = b"data") -> None:
        """Store the payload and initialize status tracking."""
        self.content = content
        self.status_checked = False

    def raise_for_status(self) -> None:
        """Record that status validation was executed."""
        self.status_checked = True


class DummySession:
    """Simple HTTP session test double collecting requested URLs."""

    def __init__(self, response: DummyResponse) -> None:
        """Initialize session with a fixed response object."""
        self.response = response
        self.calls: list[str] = []

    def get(self, url: str, timeout: tuple[float, float]) -> DummyResponse:
        """Record URL requests and return the configured response."""
        del timeout
        self.calls.append(url)
        return self.response


def _chapter(chapter_id: int, name: str, sub_title: str = "sub") -> SimpleNamespace:
    """Build a minimal chapter object."""
    return SimpleNamespace(chapter_id=chapter_id, name=name, sub_title=sub_title)


def _group(chapters: list[SimpleNamespace]) -> SimpleNamespace:
    """Build a chapter group wrapper used by title dumps."""
    return SimpleNamespace(
        first_chapter_list=list(chapters),
        mid_chapter_list=[],
        last_chapter_list=[],
    )


def _run_report() -> RunReport:
    """Return mutable run report instance compatible with downloader internals."""
    return RunReport()


def test_filter_chapters_to_download_skips_existing_files() -> None:
    """Verify existing chapter files are skipped from download candidates."""
    downloader = DummyDownloader()
    chapter_data = {
        1: {"chapter_id": 1, "sub_title": "Chapter One"},
        2: {"chapter_id": 2, "sub_title": "Chapter Two"},
    }
    chapter1 = _chapter(1, "#1")
    chapter2 = _chapter(2, "#2")
    title_dump = SimpleNamespace(chapter_list_group=[_group([chapter1, chapter2])])
    title_detail = SimpleNamespace(name="My Manga")

    existing = [downloader._build_expected_filename("My Manga", chapter1, "Chapter One")]

    result = downloader._filter_chapters_to_download(
        chapter_data,
        title_dump,
        title_detail,
        existing_files=existing,
        requested_chapter_ids={1, 2},
    )

    assert result == [2]


def test_dump_title_metadata_writes_expected_json(tmp_path: Path) -> None:
    """Verify metadata exporter writes normalized chapter metadata JSON."""
    downloader = DummyDownloader(destination=str(tmp_path))
    title_dump = SimpleNamespace(
        non_appearance_info="n/a",
        number_of_views=321,
        overview="overview",
        title=SimpleNamespace(name="my manga", author="author", portrait_image_url="http://img"),
        chapter_data={1: {"chapter_id": 1, "thumbnail_url": "t1", "sub_title": "hello/world"}},
    )

    export_dir = tmp_path / "My Manga"
    downloader._dump_title_metadata(title_dump, export_dir)

    metadata_file = export_dir / "title_metadata.json"
    assert metadata_file.exists()

    content = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert content["name"] == "my manga"
    assert content["author"] == "author"
    assert content["chapters"]["1"]["chapter_id"] == 1
    assert content["chapters"]["1"]["sub_title"] == "Hello World"


def test_dump_title_metadata_rejects_mapping_without_export_dir() -> None:
    """Verify two-argument mode requires an export directory as second value."""
    downloader = DummyDownloader()
    title_dump = SimpleNamespace(chapter_data={})

    with pytest.raises(TypeError, match="Expected export directory"):
        downloader._dump_title_metadata(title_dump, {1: {"chapter_id": 1}})


def test_dump_title_metadata_rejects_non_mapping_when_export_dir_is_provided(
    tmp_path: Path,
) -> None:
    """Verify three-argument mode requires chapter metadata mapping as second value."""
    downloader = DummyDownloader()
    title_dump = SimpleNamespace(chapter_data={})

    with pytest.raises(TypeError, match="Expected chapter metadata mapping"):
        downloader._dump_title_metadata(title_dump, str(tmp_path), tmp_path)


def test_dump_title_metadata_supports_explicit_chapter_mapping(tmp_path: Path) -> None:
    """Verify explicit ``chapter_data`` + ``export_dir`` writes metadata output."""
    downloader = DummyDownloader(destination=str(tmp_path))
    title_dump = SimpleNamespace(
        non_appearance_info="n/a",
        number_of_views=1,
        overview="overview",
        title=SimpleNamespace(name="my manga", author="author", portrait_image_url="http://img"),
    )
    chapter_data = {10: ChapterMetadata(thumbnail_url="t1", chapter_id=10, sub_title="A")}
    export_dir = tmp_path / "My Manga"

    downloader._dump_title_metadata(title_dump, chapter_data, export_dir)

    content = json.loads((export_dir / "title_metadata.json").read_text(encoding="utf-8"))
    assert content["chapters"]["10"]["chapter_id"] == 10
    assert content["chapters"]["10"]["sub_title"] == "A"


def test_process_chapter_pages_handles_double_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify DOUBLE page types are converted into ranged page indexes."""
    downloader = DummyDownloader()

    @contextmanager
    def fake_progressbar(items: list[Any], **kwargs: Any) -> Iterator[list[Any]]:
        """Yield given items without rendering a real progress bar."""
        del kwargs
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    calls: list[tuple[bytes, Any]] = []

    class FakeExporter:
        """Exporter test double recording add_image calls."""

        def skip_image(self, index: int | range) -> bool:
            """Never skip images in this test exporter."""
            del index
            return False

        def add_image(self, blob: bytes, index: int | range) -> None:
            """Record blob and page index for assertions."""
            calls.append((blob, index))

    pages = [
        SimpleNamespace(type=PageType.DOUBLE.value, image_url="u1"),
        SimpleNamespace(type=PageType.SINGLE.value, image_url="u2"),
    ]

    downloader._process_chapter_pages(pages, chapter_name="#1", exporter=FakeExporter())

    assert calls[0][0] == b"img:u1"
    assert calls[0][1] == range(0, 1)
    assert calls[1][0] == b"img:u2"
    assert calls[1][1] == 2


def test_has_last_page_detection() -> None:
    """Verify terminal page detection with and without last_page payload."""
    downloader = DummyDownloader()

    good = SimpleNamespace(pages=[SimpleNamespace(last_page=SimpleNamespace())])
    bad = SimpleNamespace(pages=[SimpleNamespace()])

    assert downloader._has_last_page(good) is True
    assert downloader._has_last_page(bad) is False


def test_download_calls_prepare_and_download() -> None:
    """Verify download() delegates to normalization and _download methods."""
    calls: dict[str, Any] = {}

    class Orchestrator(DummyDownloader):
        """Downloader double capturing orchestration method arguments."""

        def _prepare_normalized_manga_list(self, *args: Any) -> dict[int, set[int]]:
            """Capture prepare args and return a sentinel mapping."""
            calls["prepare"] = args
            return {42: {1}}

        def _download(self, mapping: dict[int, set[int]], report: RunReport) -> None:
            """Capture the mapping forwarded to _download."""
            del report
            calls["download"] = mapping

    loader = Orchestrator()
    summary = loader.download(
        title_ids={1},
        chapter_ids={2},
        min_chapter=1,
        max_chapter=5,
        last_chapter=True,
    )

    assert calls["prepare"] == ({1}, {2}, 1, 5, True)
    assert calls["download"] == {42: {1}}
    assert summary == DownloadSummary(
        downloaded=0,
        skipped_manifest=0,
        failed=0,
        failed_chapter_ids=(),
    )


def test_download_clears_run_cache_before_and_after_execution() -> None:
    """Verify download lifecycle clears run-level API cache at start and end."""
    calls: list[str] = []

    class Orchestrator(DummyDownloader):
        """Downloader double capturing run-level cache clear calls."""

        def _prepare_normalized_manga_list(self, *args: Any) -> dict[int, set[int]]:
            """Return empty mapping to keep flow deterministic."""
            del args
            return {}

        def _download(self, mapping: dict[int, set[int]], report: RunReport) -> None:
            """Record download invocation payload."""
            del mapping, report
            calls.append("download")

        def _clear_api_caches_for_run(self) -> None:
            """Record run-cache clearing hook invocation."""
            calls.append("clear_run")

    loader = Orchestrator()
    loader.download(title_ids={1}, chapter_ids=None, min_chapter=0, max_chapter=10)

    assert calls == ["clear_run", "download", "clear_run"]


def test_download_raises_interrupted_error_with_partial_summary() -> None:
    """Verify interrupted runs raise partial-summary wrapper error."""
    class Interrupting(DummyDownloader):
        """Downloader double raising keyboard interrupt after partial progress."""

        def _prepare_normalized_manga_list(self, *args: Any) -> dict[int, set[int]]:
            """Return deterministic normalized mapping."""
            del args
            return {42: {1}}

        def _download(self, mapping: dict[int, set[int]], report: RunReport) -> None:
            """Mark counters, then emulate user interrupt."""
            del mapping
            report.mark_downloaded()
            report.mark_manifest_skipped(2)
            report.mark_failed(99)
            raise KeyboardInterrupt

    loader = Interrupting()

    with pytest.raises(DownloadInterruptedError) as interrupted:
        loader.download(title_ids={1}, chapter_ids=None, min_chapter=0, max_chapter=10)

    assert interrupted.value.summary == DownloadSummary(
        downloaded=1,
        skipped_manifest=2,
        failed=1,
        failed_chapter_ids=(99,),
    )


def test_download_iterates_titles() -> None:
    """Verify _download iterates titles in insertion order with indexes."""
    calls: list[tuple[int, int, int, set[int]]] = []

    class Iterating(DummyDownloader):
        """Downloader double capturing _process_title invocations."""

        def _process_title(
            self,
            title_index: int,
            total_titles: int,
            title_id: int,
            chapter_ids: set[int],
            *,
            report: RunReport,
        ) -> None:
            """Record _process_title invocation payloads."""
            del report
            calls.append((title_index, total_titles, title_id, chapter_ids))

    loader = Iterating()
    loader._download({10: {1, 2}, 20: {3}}, report=_run_report())

    assert calls == [(1, 2, 10, {1, 2}), (2, 2, 20, {3})]


def test_process_title_with_no_chapters_to_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _process_title returns early when no chapters remain."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])

    downloader._process_title(1, 1, 10, {1}, report=_run_report())


def test_process_title_clears_title_cache_after_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify title-level cache clear hook runs after title processing."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )
    clear_calls: list[tuple[int, set[int]]] = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        downloader,
        "_clear_api_caches_for_title",
        lambda title_id, chapter_ids: clear_calls.append((title_id, set(chapter_ids))),
    )

    downloader._process_title(1, 1, 10, {1, 2}, report=_run_report())

    assert clear_calls == [(10, {1, 2})]


def test_process_title_downloads_sorted_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _process_title processes candidate chapters in sorted order."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={3: {"chapter_id": 3, "sub_title": "sub"}},
    )
    processed: list[tuple[int, int, int]] = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(
        downloader,
        "_extract_chapter_data",
        lambda _dump: {3: {"chapter_id": 3, "sub_title": "sub"}},
        raising=False,
    )
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [5, 2, 3])
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda title, index, total, chapter_id, **kwargs: processed.append((index, total, chapter_id)),
    )

    downloader._process_title(1, 1, 10, {2, 3, 5}, report=_run_report())

    assert processed == [(1, 3, 2), (2, 3, 3), (3, 3, 5)]


def test_process_title_dumps_metadata_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify metadata export is invoked when loader meta flag is enabled."""
    downloader = FullDownloader()
    downloader.meta = True
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )
    calls = {"metadata": 0}

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        downloader,
        "_dump_title_metadata",
        lambda *_args, **_kwargs: calls.__setitem__("metadata", calls["metadata"] + 1),
    )

    downloader._process_title(1, 1, 10, {1}, report=_run_report())

    assert calls["metadata"] == 1


def test_process_title_skips_manifest_completed_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify title processing excludes chapter IDs marked completed in manifest."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )
    processed: list[int] = []

    class FakeManifest:
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            """Store nothing; behavior is fully deterministic for the test."""
            del autosave

        def is_completed(self, chapter_id: int) -> bool:
            """Mark chapter 2 as already completed."""
            return chapter_id == 2

        def flush(self) -> None:
            """No-op flush for downloader finalize hooks."""

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2, 3])
    monkeypatch.setattr(
        "mloader.manga_loader.downloader.TitleDownloadManifest",
        FakeManifest,
    )
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda _title, _index, _total, chapter_id, **kwargs: processed.append(chapter_id),
    )

    report = _run_report()
    downloader._process_title(1, 1, 10, {1, 2, 3}, report=report)

    assert processed == [1, 3]
    assert report.skipped_manifest == 1


def test_process_title_records_failed_chapter_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify per-chapter failures are collected and run continues."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )
    processed: list[int] = []
    marked_failed: list[int] = []
    flush_calls = 0

    class FakeManifest:
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            del autosave

        def is_completed(self, chapter_id: int) -> bool:
            del chapter_id
            return False

        def mark_failed(self, chapter_id: int, *, error: str) -> None:
            del error
            marked_failed.append(chapter_id)

        def flush(self) -> None:
            nonlocal flush_calls
            flush_calls += 1

    def _process_chapter(
        _title: Any,
        _index: int,
        _total: int,
        chapter_id: int,
        **kwargs: Any,
    ) -> None:
        del kwargs
        if chapter_id == 2:
            raise RuntimeError("boom")
        processed.append(chapter_id)

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2, 3])
    monkeypatch.setattr(
        "mloader.manga_loader.downloader.TitleDownloadManifest",
        FakeManifest,
    )
    monkeypatch.setattr(downloader, "_process_chapter", _process_chapter)

    report = _run_report()
    downloader._process_title(1, 1, 10, {1, 2, 3}, report=report)

    assert processed == [1, 3]
    assert report.downloaded == 2
    assert report.failed == 1
    assert report.failed_chapter_ids == [2]
    assert marked_failed == [2]
    assert flush_calls >= 2


def test_process_title_on_keyboard_interrupt_marks_manifest_and_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify interrupt during chapter processing marks failure, flushes, and re-raises."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )
    marked_failed: list[int] = []
    flush_calls = 0

    class FakeManifest:
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            del autosave

        def is_completed(self, chapter_id: int) -> bool:
            del chapter_id
            return False

        def mark_failed(self, chapter_id: int, *, error: str) -> None:
            del error
            marked_failed.append(chapter_id)

        def flush(self) -> None:
            nonlocal flush_calls
            flush_calls += 1

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1])
    monkeypatch.setattr(
        "mloader.manga_loader.downloader.TitleDownloadManifest",
        FakeManifest,
    )
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    report = _run_report()
    with pytest.raises(KeyboardInterrupt):
        downloader._process_title(1, 1, 10, {1}, report=report)

    assert report.failed == 1
    assert report.failed_chapter_ids == [1]
    assert marked_failed == [1]
    assert flush_calls >= 2


def test_process_title_resume_skips_completed_and_retries_failed_after_restart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify manifest resume across two runs skips completed and retries failed chapters."""
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )

    first_run = FullDownloader(destination=str(tmp_path))
    first_attempts: list[int] = []

    def _first_process_chapter(
        _title: Any,
        _index: int,
        _total: int,
        chapter_id: int,
        **kwargs: Any,
    ) -> None:
        manifest = kwargs.get("manifest")
        first_attempts.append(chapter_id)
        if chapter_id == 2:
            raise RuntimeError("boom")
        if manifest is not None:
            manifest.mark_completed(chapter_id)

    monkeypatch.setattr(first_run, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(first_run, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(first_run, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(first_run, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2])
    monkeypatch.setattr(first_run, "_process_chapter", _first_process_chapter)

    first_report = _run_report()
    first_run._process_title(1, 1, 10, {1, 2}, report=first_report)

    assert first_attempts == [1, 2]
    assert first_report.downloaded == 1
    assert first_report.failed == 1
    assert first_report.failed_chapter_ids == [2]

    second_run = FullDownloader(destination=str(tmp_path))
    second_attempts: list[int] = []

    monkeypatch.setattr(second_run, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(second_run, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(second_run, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(second_run, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2])
    monkeypatch.setattr(
        second_run,
        "_process_chapter",
        lambda _title, _index, _total, chapter_id, **kwargs: second_attempts.append(chapter_id),
    )

    second_report = _run_report()
    second_run._process_title(1, 1, 10, {1, 2}, report=second_report)

    assert second_attempts == [2]
    assert second_report.downloaded == 1
    assert second_report.skipped_manifest == 1
    assert second_report.failed == 0


def test_process_title_disables_manifest_when_resume_is_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --no-resume mode skips manifest-based chapter filtering."""
    downloader = FullDownloader()
    downloader.resume = False
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )
    processed: list[int] = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [1, 2])
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda _title, _index, _total, chapter_id, **kwargs: processed.append(chapter_id),
    )

    report = _run_report()
    downloader._process_title(1, 1, 10, {1, 2}, report=report)

    assert processed == [1, 2]
    assert report.skipped_manifest == 0


def test_process_title_resets_manifest_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --manifest-reset clears existing per-title manifest state."""
    downloader = FullDownloader()
    downloader.manifest_reset = True
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )
    reset_calls = 0

    class FakeManifest:
        def __init__(self, _export_path: Path, *, autosave: bool = False) -> None:
            del autosave

        def reset(self) -> None:
            nonlocal reset_calls
            reset_calls += 1

        def is_completed(self, chapter_id: int) -> bool:
            del chapter_id
            return False

        def flush(self) -> None:
            """No-op flush for downloader finalize hooks."""

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "mloader.manga_loader.downloader.TitleDownloadManifest",
        FakeManifest,
    )

    downloader._process_title(1, 1, 10, {1}, report=_run_report())

    assert reset_calls == 1


def test_process_chapter_raises_when_subscription_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _process_chapter raises subscription error without last_page payload."""
    downloader = FullDownloader()
    viewer = SimpleNamespace(chapter_name="C1", pages=[SimpleNamespace()])
    monkeypatch.setattr(downloader, "_load_pages", lambda _cid: viewer, raising=False)

    with pytest.raises(SubscriptionRequiredError):
        downloader._process_chapter(SimpleNamespace(name="t"), 1, 1, 10)


def test_process_chapter_creates_exporter_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _process_chapter builds exporter, processes pages, and closes exporter."""

    class ExporterInstance:
        """Exporter test double with close tracking."""

        def __init__(self) -> None:
            """Initialize close tracking state."""
            self.closed = False

        def close(self) -> None:
            """Record close invocation."""
            self.closed = True

    instance = ExporterInstance()
    captured: dict[str, Any] = {}
    started: list[tuple[int, str, str, str]] = []
    completed: list[tuple[int, str | None]] = []

    class Manifest:
        def mark_started(
            self,
            chapter_id: int,
            *,
            chapter_name: str,
            sub_title: str,
            output_format: str,
        ) -> None:
            started.append((chapter_id, chapter_name, sub_title, output_format))

        def mark_completed(self, chapter_id: int, *, output_path: str | None = None) -> None:
            completed.append((chapter_id, output_path))

    def exporter_factory(**kwargs: Any) -> ExporterInstance:
        """Capture exporter constructor arguments and return test instance."""
        captured.update(kwargs)
        return instance

    downloader = FullDownloader()
    downloader.exporter = exporter_factory
    processed: list[tuple[list[Any], str, Any]] = []

    viewer = SimpleNamespace(
        chapter_name="#1",
        pages=[
            SimpleNamespace(manga_page=SimpleNamespace(image_url="u1")),
            SimpleNamespace(
                manga_page=SimpleNamespace(image_url=""),
                last_page=SimpleNamespace(
                    current_chapter=SimpleNamespace(name="#1", sub_title="Sub"),
                    next_chapter=SimpleNamespace(chapter_id=0),
                ),
            ),
        ],
    )

    monkeypatch.setattr(downloader, "_load_pages", lambda _cid: viewer, raising=False)
    monkeypatch.setattr(
        downloader,
        "_process_chapter_pages",
        lambda pages, chapter_name, exporter: processed.append((pages, chapter_name, exporter)),
    )

    title = SimpleNamespace(name="My Manga")
    downloader._process_chapter(title, 1, 1, 10, manifest=Manifest())

    assert captured["title"] is title
    assert captured["chapter"].sub_title == "Sub"
    assert captured["next_chapter"] is None
    assert processed[0][1] == "#1"
    assert len(processed[0][0]) == 1
    assert instance.closed is True
    assert started == [(10, "#1", "Sub", "pdf")]
    assert completed == [(10, None)]


def test_process_chapter_marks_manifest_failed_when_page_processing_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chapter export-processing failures are raised to title-level handling."""
    downloader = FullDownloader()

    class Exporter:
        def close(self) -> None:
            """No-op close used by this failure-path test."""

    class Manifest:
        def mark_started(
            self,
            chapter_id: int,
            *,
            chapter_name: str,
            sub_title: str,
            output_format: str,
        ) -> None:
            del chapter_id, chapter_name, sub_title, output_format

    viewer = SimpleNamespace(
        chapter_name="#1",
        pages=[
            SimpleNamespace(manga_page=SimpleNamespace(image_url="u1")),
            SimpleNamespace(
                manga_page=SimpleNamespace(image_url=""),
                last_page=SimpleNamespace(
                    current_chapter=SimpleNamespace(name="#1", sub_title="Sub"),
                    next_chapter=SimpleNamespace(chapter_id=0),
                ),
            ),
        ],
    )

    monkeypatch.setattr(downloader, "_load_pages", lambda _cid: viewer, raising=False)
    monkeypatch.setattr(downloader, "exporter", lambda **kwargs: Exporter())
    monkeypatch.setattr(
        downloader,
        "_process_chapter_pages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="boom"):
        downloader._process_chapter(SimpleNamespace(name="My Manga"), 1, 1, 10, manifest=Manifest())


def test_download_image_calls_raise_for_status() -> None:
    """Verify _download_image calls response.raise_for_status before returning bytes."""
    downloader = FullDownloader()
    response = DummyResponse(content=b"img")
    session = DummySession(response)
    downloader.session = session

    result = downloader._download_image("http://img")

    assert session.calls == ["http://img"]
    assert response.status_checked is True
    assert result == b"img"


def test_process_chapter_pages_skips_when_exporter_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _process_chapter_pages skips add_image when exporter says to skip."""
    downloader = DummyDownloader()

    @contextmanager
    def fake_progressbar(items: list[Any], **kwargs: Any) -> Iterator[list[Any]]:
        """Yield given items without rendering a real progress bar."""
        del kwargs
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    class SkipExporter:
        """Exporter test double that always skips images."""

        def skip_image(self, index: int | range) -> bool:
            """Return True for every page index."""
            del index
            return True

        def add_image(self, blob: bytes, index: int | range) -> None:
            """Fail test if add_image is called while skip_image is True."""
            del blob, index
            raise AssertionError("add_image should not be called when skip_image is True")

    pages = [SimpleNamespace(type=PageType.SINGLE.value, image_url="u1")]
    downloader._process_chapter_pages(pages, chapter_name="#1", exporter=SkipExporter())


def test_process_chapter_pages_uses_decrypt_for_encrypted_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify encrypted pages route through decrypt path before export."""
    downloader = DummyDownloader()

    @contextmanager
    def fake_progressbar(items: list[Any], **kwargs: Any) -> Iterator[list[Any]]:
        """Yield given items without rendering a real progress bar."""
        del kwargs
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    captured: list[bytes] = []

    class CapturingExporter:
        """Exporter test double collecting written image bytes."""

        def skip_image(self, index: int | range) -> bool:
            """Never skip pages in this test."""
            del index
            return False

        def add_image(self, blob: bytes, index: int | range) -> None:
            """Store output image blobs for assertion."""
            del index
            captured.append(blob)

    pages = [
        SimpleNamespace(type=PageType.SINGLE.value, image_url="u1", encryption_key="abcd"),
        SimpleNamespace(type=PageType.SINGLE.value, image_url="u2", encryption_key=""),
    ]
    downloader._process_chapter_pages(pages, chapter_name="#1", exporter=CapturingExporter())

    assert captured == [b"dec:u1:abcd", b"img:u2"]


def test_extract_chapter_data_from_all_groups() -> None:
    """Verify chapter metadata extraction includes first/mid/last chapter groups."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        chapter_list_group=[
            SimpleNamespace(
                first_chapter_list=[SimpleNamespace(sub_title="A", thumbnail_url="t1", chapter_id=1)],
                mid_chapter_list=[SimpleNamespace(sub_title="B", thumbnail_url="t2", chapter_id=2)],
                last_chapter_list=[SimpleNamespace(sub_title="C", thumbnail_url="t3", chapter_id=3)],
            )
        ]
    )

    result = downloader._extract_chapter_data(title_dump)

    assert result[1]["chapter_id"] == 1
    assert result[2]["chapter_id"] == 2
    assert result[3]["chapter_id"] == 3
    assert result[2]["sub_title"] == "B"


def test_extract_chapter_data_keeps_duplicate_subtitles_by_chapter_id() -> None:
    """Verify duplicate subtitles do not overwrite chapter metadata entries."""
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        chapter_list_group=[
            SimpleNamespace(
                first_chapter_list=[
                    SimpleNamespace(sub_title="Same", thumbnail_url="t1", chapter_id=1),
                    SimpleNamespace(sub_title="Same", thumbnail_url="t2", chapter_id=2),
                ],
                mid_chapter_list=[],
                last_chapter_list=[],
            )
        ]
    )

    result = downloader._extract_chapter_data(title_dump)

    assert set(result.keys()) == {1, 2}
    assert result[1]["sub_title"] == "Same"
    assert result[2]["sub_title"] == "Same"


def test_get_existing_files_returns_stems(tmp_path: Path) -> None:
    """Verify _get_existing_files returns PDF stems only."""
    downloader = DummyDownloader()
    export_path = tmp_path / "manga"
    export_path.mkdir()
    (export_path / "a.pdf").write_bytes(b"1")
    (export_path / "b.pdf").write_bytes(b"2")
    (export_path / "c.cbz").write_bytes(b"3")

    assert sorted(downloader._get_existing_files(export_path)) == ["a", "b"]


def test_get_existing_files_returns_empty_when_missing(tmp_path: Path) -> None:
    """Verify _get_existing_files returns empty list for missing export path."""
    downloader = DummyDownloader()
    assert downloader._get_existing_files(tmp_path / "missing") == []


def test_get_existing_files_uses_cbz_extension(tmp_path: Path) -> None:
    """Verify existing chapter lookup uses cbz extension in CBZ mode."""
    downloader = DummyDownloader()
    downloader.output_format = "cbz"
    export_path = tmp_path / "manga"
    export_path.mkdir()
    (export_path / "a.cbz").write_bytes(b"1")
    (export_path / "b.pdf").write_bytes(b"2")

    assert downloader._get_existing_files(export_path) == ["a"]


def test_get_existing_files_is_disabled_for_raw_mode(tmp_path: Path) -> None:
    """Verify raw mode disables chapter-level existing-file prefiltering."""
    downloader = DummyDownloader()
    downloader.output_format = "raw"
    export_path = tmp_path / "manga"
    export_path.mkdir()
    (export_path / "a.pdf").write_bytes(b"1")

    assert downloader._get_existing_files(export_path) == []


def test_filter_chapters_warns_when_chapter_missing(caplog: Any) -> None:
    """Verify missing chapter IDs log a warning and are excluded."""
    downloader = DummyDownloader()
    chapter_data = {99: {"chapter_id": 99, "sub_title": "Missing"}}
    title_dump = SimpleNamespace(chapter_list_group=[])
    title_detail = SimpleNamespace(name="My Manga")

    with caplog.at_level("WARNING"):
        result = downloader._filter_chapters_to_download(
            chapter_data,
            title_dump,
            title_detail,
            existing_files=[],
            requested_chapter_ids={99},
        )

    assert result == []
    assert "not found in title dump" in caplog.text


def test_filter_chapters_accepts_dataclass_metadata_values() -> None:
    """Verify chapter filtering accepts ``ChapterMetadata`` objects directly."""
    downloader = DummyDownloader()
    chapter = _chapter(5, "#5")
    title_dump = SimpleNamespace(chapter_list_group=[_group([chapter])])
    title_detail = SimpleNamespace(name="My Manga")
    chapter_data = {5: ChapterMetadata(thumbnail_url="t5", chapter_id=5, sub_title="Sub")}

    result = downloader._filter_chapters_to_download(
        chapter_data,
        title_dump,
        title_detail,
        existing_files=[],
        requested_chapter_ids={5},
    )

    assert result == [5]


def test_download_mixin_placeholders_raise_not_implemented() -> None:
    """Verify abstract data-loader placeholders raise ``NotImplementedError``."""
    with pytest.raises(NotImplementedError):
        DownloadMixin._prepare_normalized_manga_list(None, None, None, 0, 0, False)  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError):
        DownloadMixin._get_title_details(None, 1)  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError):
        DownloadMixin._load_pages(None, 1)  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError):
        DownloadMixin._decrypt_image(None, "http://img", "ab")  # type: ignore[arg-type]


def test_chapter_metadata_mapping_access_and_key_error() -> None:
    """Verify compatibility mapping access on ``ChapterMetadata``."""
    metadata = ChapterMetadata(thumbnail_url="thumb", chapter_id=7, sub_title="Sub")

    assert metadata["thumbnail_url"] == "thumb"
    assert metadata["sub_title"] == "Sub"
    with pytest.raises(KeyError):
        _ = metadata["unknown"]


def test_find_chapter_by_id_returns_match_and_none() -> None:
    """Verify chapter lookup returns chapter object when found, else None."""
    downloader = DummyDownloader()
    chapter = _chapter(1, "#1")
    title_dump = SimpleNamespace(chapter_list_group=[_group([chapter])])

    assert downloader._find_chapter_by_id(title_dump, 1) is chapter
    assert downloader._find_chapter_by_id(title_dump, 2) is None


def test_prepare_filename_keeps_text_when_mojibake_fix_fails() -> None:
    """Verify filename sanitizer still returns safe text on decode failures."""
    downloader = DummyDownloader()
    assert downloader._prepare_filename("A\u20ac!") == "A"
