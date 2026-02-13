import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import click

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
