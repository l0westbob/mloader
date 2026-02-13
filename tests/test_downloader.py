import json
from contextlib import contextmanager
from types import SimpleNamespace

import click
import pytest

from mloader.constants import PageType
from mloader.manga_loader.downloader import DownloadMixin


class DummyDownloader(DownloadMixin):
    def __init__(self, destination="/tmp/out"):
        self.exporter = SimpleNamespace(keywords={"destination": destination})
        self.meta = False

    def _extract_chapter_data(self, title_dump):
        return title_dump.chapter_data

    def _download_image(self, url):
        return f"img:{url}".encode("utf-8")


class FullDownloader(DownloadMixin):
    def __init__(self, destination="/tmp/out"):
        self.exporter = SimpleNamespace(keywords={"destination": destination})
        self.meta = False
        self.session = DummySession(DummyResponse(content=b"default"))


class DummyResponse:
    def __init__(self, content=b"data"):
        self.content = content
        self.status_checked = False

    def raise_for_status(self):
        self.status_checked = True


class DummySession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return self.response


def _chapter(chapter_id, name, sub_title="sub"):
    return SimpleNamespace(chapter_id=chapter_id, name=name, sub_title=sub_title)


def _group(chapters):
    return SimpleNamespace(
        first_chapter_list=list(chapters),
        mid_chapter_list=[],
        last_chapter_list=[],
    )


def test_filter_chapters_to_download_skips_existing_files():
    downloader = DummyDownloader()
    chapter_data = {
        "Chapter One": {"chapter_id": 1},
        "Chapter Two": {"chapter_id": 2},
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


def test_dump_title_metadata_writes_expected_json(tmp_path):
    downloader = DummyDownloader(destination=str(tmp_path))
    title_dump = SimpleNamespace(
        non_appearance_info="n/a",
        number_of_views=321,
        overview="overview",
        title=SimpleNamespace(name="my manga", author="author", portrait_image_url="http://img"),
        chapter_data={"hello/world": {"chapter_id": 1, "thumbnail_url": "t1"}},
    )

    export_dir = tmp_path / "My Manga"
    downloader._dump_title_metadata(title_dump, export_dir)

    metadata_file = export_dir / "title_metadata.json"
    assert metadata_file.exists()

    content = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert content["name"] == "my manga"
    assert content["author"] == "author"
    assert content["chapters"]["Hello World"]["chapter_id"] == 1


def test_process_chapter_pages_handles_double_pages(monkeypatch):
    downloader = DummyDownloader()

    @contextmanager
    def fake_progressbar(items, **kwargs):
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    calls = []

    class FakeExporter:
        def skip_image(self, index):
            return False

        def add_image(self, blob, index):
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


def test_has_last_page_detection():
    downloader = DummyDownloader()

    good = SimpleNamespace(pages=[SimpleNamespace(last_page=SimpleNamespace())])
    bad = SimpleNamespace(pages=[SimpleNamespace()])

    assert downloader._has_last_page(good) is True
    assert downloader._has_last_page(bad) is False


def test_download_calls_prepare_and_download():
    calls = {}

    class Orchestrator(DummyDownloader):
        def _prepare_normalized_manga_list(self, *args):
            calls["prepare"] = args
            return {"mapping": {1}}

        def _download(self, mapping):
            calls["download"] = mapping

    loader = Orchestrator()
    loader.download(title_ids={1}, chapter_ids={2}, min_chapter=1, max_chapter=5, last_chapter=True)

    assert calls["prepare"] == ({1}, {2}, 1, 5, True)
    assert calls["download"] == {"mapping": {1}}


def test_download_iterates_titles():
    calls = []

    class Iterating(DummyDownloader):
        def _process_title(self, title_index, total_titles, title_id, chapter_ids):
            calls.append((title_index, total_titles, title_id, chapter_ids))

    loader = Iterating()
    loader._download({10: {1, 2}, 20: {3}})

    assert calls == [(1, 2, 10, {1, 2}), (2, 2, 20, {3})]


def test_process_title_with_no_chapters_to_download(monkeypatch):
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={},
    )

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(downloader, "_extract_chapter_data", lambda _dump: {}, raising=False)
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [])

    downloader._process_title(1, 1, 10, {1})


def test_process_title_downloads_sorted_chapters(monkeypatch):
    downloader = FullDownloader()
    title_dump = SimpleNamespace(
        title=SimpleNamespace(name="My Manga", author="A"),
        chapter_data={"sub": {"chapter_id": 3}},
    )
    processed = []

    monkeypatch.setattr(downloader, "_get_title_details", lambda _tid: title_dump, raising=False)
    monkeypatch.setattr(
        downloader,
        "_extract_chapter_data",
        lambda _dump: {"sub": {"chapter_id": 3}},
        raising=False,
    )
    monkeypatch.setattr(downloader, "_get_existing_files", lambda _path: [])
    monkeypatch.setattr(downloader, "_filter_chapters_to_download", lambda *args, **kwargs: [5, 2, 3])
    monkeypatch.setattr(
        downloader,
        "_process_chapter",
        lambda title, index, total, chapter_id: processed.append((index, total, chapter_id)),
    )

    downloader._process_title(1, 1, 10, {2, 3, 5})

    assert processed == [(1, 3, 2), (2, 3, 3), (3, 3, 5)]


def test_process_title_dumps_metadata_when_enabled(monkeypatch):
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

    downloader._process_title(1, 1, 10, {1})

    assert calls["metadata"] == 1


def test_process_chapter_exits_without_last_page(monkeypatch):
    downloader = FullDownloader()
    viewer = SimpleNamespace(chapter_name="C1", pages=[SimpleNamespace()])
    monkeypatch.setattr(downloader, "_load_pages", lambda _cid: viewer, raising=False)

    with pytest.raises(SystemExit):
        downloader._process_chapter(SimpleNamespace(name="t"), 1, 1, 10)


def test_process_chapter_creates_exporter_and_closes(monkeypatch):
    class ExporterInstance:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    instance = ExporterInstance()
    captured = {}

    def exporter_factory(**kwargs):
        captured.update(kwargs)
        return instance

    downloader = FullDownloader()
    downloader.exporter = exporter_factory
    processed = []

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
    downloader._process_chapter(title, 1, 1, 10)

    assert captured["title"] is title
    assert captured["chapter"].sub_title == "Sub"
    assert captured["next_chapter"] is None
    assert processed[0][1] == "#1"
    assert len(processed[0][0]) == 1
    assert instance.closed is True


def test_download_image_calls_raise_for_status():
    downloader = FullDownloader()
    response = DummyResponse(content=b"img")
    session = DummySession(response)
    downloader.session = session

    result = downloader._download_image("http://img")

    assert session.calls == ["http://img"]
    assert response.status_checked is True
    assert result == b"img"


def test_process_chapter_pages_skips_when_exporter_requests(monkeypatch):
    downloader = DummyDownloader()

    @contextmanager
    def fake_progressbar(items, **kwargs):
        yield items

    monkeypatch.setattr(click, "progressbar", fake_progressbar)

    class SkipExporter:
        def skip_image(self, index):
            return True

        def add_image(self, blob, index):
            raise AssertionError("add_image should not be called when skip_image is True")

    pages = [SimpleNamespace(type=PageType.SINGLE.value, image_url="u1")]
    downloader._process_chapter_pages(pages, chapter_name="#1", exporter=SkipExporter())


def test_extract_chapter_data_from_all_groups():
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

    assert result["A"]["chapter_id"] == 1
    assert result["B"]["chapter_id"] == 2
    assert result["C"]["chapter_id"] == 3


def test_get_existing_files_returns_stems(tmp_path):
    downloader = DummyDownloader()
    export_path = tmp_path / "manga"
    export_path.mkdir()
    (export_path / "a.pdf").write_bytes(b"1")
    (export_path / "b.pdf").write_bytes(b"2")
    (export_path / "c.cbz").write_bytes(b"3")

    assert sorted(downloader._get_existing_files(export_path)) == ["a", "b"]


def test_get_existing_files_returns_empty_when_missing(tmp_path):
    downloader = DummyDownloader()
    assert downloader._get_existing_files(tmp_path / "missing") == []


def test_filter_chapters_warns_when_chapter_missing(caplog):
    downloader = DummyDownloader()
    chapter_data = {"Missing": {"chapter_id": 99}}
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


def test_find_chapter_by_id_returns_match_and_none():
    downloader = DummyDownloader()
    chapter = _chapter(1, "#1")
    title_dump = SimpleNamespace(chapter_list_group=[_group([chapter])])

    assert downloader._find_chapter_by_id(title_dump, 1) is chapter
    assert downloader._find_chapter_by_id(title_dump, 2) is None


def test_prepare_filename_keeps_text_when_mojibake_fix_fails():
    downloader = DummyDownloader()
    assert downloader._prepare_filename("A\u20ac!") == "A"
