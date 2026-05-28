"""Replay tests using real captured API payload fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import pytest

from mloader.domain.planning import build_download_plan
from mloader.infrastructure.mangaplus import parsing
from mloader.manga_loader.chapter_planning import ChapterPlanner
from mloader.manga_loader.init import MangaLoader
from mloader.types import ChapterLike, ExporterLike, PageIndex, ResponseLike, SessionLike, TitleLike
from mloader.utils import escape_path

FIXTURE_CAPTURE_DIR = Path(__file__).parent / "fixtures" / "api_captures" / "baseline"
LOCAL_CAPTURE_DIR = Path("capture")


def _as_dict(value: object, context: str) -> dict[str, Any]:
    """Return ``value`` as a dictionary or raise a descriptive assertion error."""
    if not isinstance(value, dict):
        raise AssertionError(f"Expected dict for {context}, got {type(value).__name__}")
    return cast(dict[str, Any], value)


def _as_list(value: object, context: str) -> list[Any]:
    """Return ``value`` as a list or raise a descriptive assertion error."""
    if not isinstance(value, list):
        raise AssertionError(f"Expected list for {context}, got {type(value).__name__}")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    """Load and return JSON object from ``path``."""
    return _as_dict(json.loads(path.read_text(encoding="utf-8")), str(path))


def _collect_capture_records(
    capture_dir: Path,
) -> list[tuple[str, dict[str, Any], dict[str, Any] | None]]:
    """Collect capture metadata/response records from ``capture_dir``."""
    records: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = []
    for meta_path in sorted(capture_dir.glob("*.meta.json")):
        stem = meta_path.name.removesuffix(".meta.json")
        meta = _load_json(meta_path)
        response_path = capture_dir / f"{stem}.response.json"
        if response_path.exists():
            response: dict[str, Any] | None = _load_json(response_path)
        elif meta.get("payload_classification") == "api_error":
            response = None
        else:
            raise AssertionError(f"Missing response JSON for capture stem: {stem}")
        records.append((stem, meta, response))
    return records


def _schema_signature(
    meta: dict[str, Any],
    response: dict[str, Any] | None,
) -> dict[str, object]:
    """Build a schema signature from capture metadata and parsed response JSON."""
    endpoint = str(meta["endpoint"])
    signature: dict[str, object] = {
        "endpoint": endpoint,
        "url_path": urlparse(str(meta["url"])).path,
        "meta_keys": sorted(meta.keys()),
        "param_keys": sorted(_as_dict(meta["params"], "meta.params").keys()),
    }

    if meta.get("payload_classification") == "api_error":
        api_error = _as_dict(meta.get("api_error"), "meta.api_error")
        signature["payload_classification"] = "api_error"
        signature["api_error_code"] = api_error.get("code")
        signature["api_error_language"] = api_error.get("language")
        signature["api_error_title"] = api_error.get("title")
        return signature

    if response is None:
        raise AssertionError(f"Missing response JSON for successful endpoint: {endpoint}")

    success = _as_dict(response["success"], "response.success")
    signature["success_keys"] = sorted(success.keys())

    if endpoint == "manga_viewer":
        viewer = _as_dict(success["manga_viewer"], "response.success.manga_viewer")
        signature["payload_keys"] = sorted(viewer.keys())

        pages = _as_list(viewer.get("pages", []), "response.success.manga_viewer.pages")
        if meta.get("expected_runtime_error") == "subscription_required":
            signature["payload_state"] = "subscription_required"
            return signature

        signature["payload_state"] = "pages"
        first_page = _as_dict(pages[0], "response.success.manga_viewer.pages[0]")
        last_page = _as_dict(pages[-1], "response.success.manga_viewer.pages[-1]")
        signature["first_page_keys"] = sorted(first_page.keys())
        signature["last_page_keys"] = sorted(last_page.keys())
        signature["manga_page_keys"] = sorted(
            _as_dict(
                first_page["manga_page"], "response.success.manga_viewer.pages[0].manga_page"
            ).keys()
        )
        signature["last_page_payload_keys"] = sorted(
            _as_dict(
                last_page["last_page"], "response.success.manga_viewer.pages[-1].last_page"
            ).keys()
        )
        return signature

    if endpoint == "title_detailV3":
        title_detail = _as_dict(success["title_detail_view"], "response.success.title_detail_view")
        signature["payload_keys"] = sorted(title_detail.keys())
        signature["title_keys"] = sorted(
            _as_dict(title_detail["title"], "response.success.title_detail_view.title").keys()
        )

        chapter_groups = title_detail.get("chapter_list_group")
        if chapter_groups:
            grouped_chapters = _as_list(
                chapter_groups,
                "response.success.title_detail_view.chapter_list_group",
            )
            first_group = _as_dict(
                grouped_chapters[0],
                "response.success.title_detail_view.chapter_list_group[0]",
            )
            signature["chapter_source"] = "chapter_list_group"
            signature["chapter_group_keys"] = sorted(first_group.keys())

            first_chapter_list = _as_list(
                first_group["first_chapter_list"], "chapter_group.first_chapter_list"
            )
            first_chapter = _as_dict(first_chapter_list[0], "chapter_group.first_chapter_list[0]")
            signature["chapter_keys"] = sorted(first_chapter.keys())
            return signature

        flat_chapters = _as_list(
            title_detail.get("chapter_list", []),
            "response.success.title_detail_view.chapter_list",
        )
        signature["chapter_source"] = "chapter_list"
        first_chapter = _as_dict(flat_chapters[0], "title_detail.chapter_list[0]")
        signature["chapter_keys"] = sorted(first_chapter.keys())
        return signature

    if endpoint == "title_index":
        all_titles = _as_dict(success["all_titles_view"], "response.success.all_titles_view")
        signature["payload_keys"] = sorted(all_titles.keys())
        title_groups = _as_list(
            all_titles["title_groups"],
            "response.success.all_titles_view.title_groups",
        )
        first_group = _as_dict(title_groups[0], "all_titles_view.title_groups[0]")
        signature["title_group_keys"] = sorted(first_group.keys())
        titles = _as_list(first_group["titles"], "all_titles_view.title_groups[0].titles")
        first_title = _as_dict(titles[0], "all_titles_view.title_groups[0].titles[0]")
        signature["title_keys"] = sorted(first_title.keys())
        return signature

    raise AssertionError(f"Unexpected endpoint in capture metadata: {endpoint}")


def test_title_detail_fixture_replays_into_chapter_planner() -> None:
    """Validate chapter planning logic against a real captured title-detail payload."""
    raw_payload = (FIXTURE_CAPTURE_DIR / "0001_title_detailV3_100010.pb").read_bytes()
    title_detail = parsing.parse_title_detail_response(raw_payload)

    assert title_detail.title.title_id == 100010
    assert title_detail.title.name == "Dr. STONE"

    chapter_data = ChapterPlanner.extract_chapter_data(title_detail, lambda value: value)
    assert len(chapter_data) == 236

    chapter_2 = ChapterPlanner.find_chapter_by_id(title_detail, 1000311)
    assert chapter_2 is not None
    expected_existing = ChapterPlanner.build_expected_filename(
        escape_path(title_detail.title.name).title(),
        chapter_2,
        chapter_2.sub_title,
    )

    result = ChapterPlanner.filter_chapters_to_download(
        chapter_data=chapter_data,
        title_detail=title_detail,
        existing_files=[expected_existing],
        requested_chapter_ids={1000311, 1000312},
    )
    assert result == [1000312]


def test_capture_replay_dto_plan_and_filename_contract() -> None:
    """Replay fixtures through DTO mapping, domain planning, and filename filtering."""
    title_detail = parsing.parse_title_detail_response(
        (FIXTURE_CAPTURE_DIR / "0001_title_detailV3_100010.pb").read_bytes()
    )
    viewer_by_id = {
        1000311: parsing.parse_manga_viewer_response(
            (FIXTURE_CAPTURE_DIR / "0002_manga_viewer_1000311.pb").read_bytes()
        ),
    }

    plan = build_download_plan(
        title_ids={100010},
        chapter_numbers={3},
        chapter_ids={1000311},
        min_chapter=0,
        max_chapter=999,
        last_chapter=False,
        load_title_detail=lambda title_id: (
            title_detail
            if title_id == 100010
            else pytest.fail(f"Unexpected title load: {title_id}")
        ),
        load_viewer=lambda chapter_id: viewer_by_id[chapter_id],
    )

    assert plan.title_count == 1
    title_plan = plan.title_plans[0]
    assert title_plan.title_detail.__class__.__module__ == "mloader.domain.manga"
    assert title_plan.chapter_ids == frozenset({1000311, 1000312})

    chapter_data = ChapterPlanner.extract_chapter_data(title_plan.title_detail, escape_path)
    filename_by_id = {
        chapter.chapter_id: ChapterPlanner.build_expected_filename(
            escape_path(title_plan.title_detail.title.name).title(),
            chapter,
            chapter_data[chapter.chapter_id].sub_title,
        )
        for chapter in title_plan.selected_chapters
    }

    assert filename_by_id == {
        1000311: "Dr Stone - 002 - Z 2 Fantasy vs Science",
        1000312: "Dr Stone - 003 - Z 3 King of the Stone World",
    }
    assert ChapterPlanner.filter_chapters_to_download(
        chapter_data=chapter_data,
        title_detail=title_plan.title_detail,
        existing_files=[filename_by_id[1000311]],
        requested_chapter_ids=title_plan.chapter_ids,
    ) == [1000312]


@pytest.mark.parametrize(
    ("fixture_name", "chapter_id", "next_chapter_id"),
    [
        ("0002_manga_viewer_1000311.pb", 1000311, 1000312),
        ("0003_manga_viewer_1000312.pb", 1000312, 1000313),
    ],
)
def test_manga_viewer_fixtures_replay_consistently(
    fixture_name: str,
    chapter_id: int,
    next_chapter_id: int,
) -> None:
    """Validate real manga-viewer fixture parsing for chapter linkage."""
    raw_payload = (FIXTURE_CAPTURE_DIR / fixture_name).read_bytes()
    viewer = parsing.parse_manga_viewer_response(raw_payload)

    assert viewer.title_id == 100010
    assert viewer.chapter_id == chapter_id
    assert len(viewer.pages) > 20
    assert len(viewer.chapters) == 3

    last_page = viewer.last_page
    assert last_page is not None
    assert last_page.current_chapter.chapter_id == chapter_id
    assert last_page.next_chapter is not None
    assert last_page.next_chapter.chapter_id == next_chapter_id


def test_local_capture_schema_matches_baseline_fixture() -> None:
    """Compare local capture schema against baseline fixture schema signatures."""
    baseline_records = _collect_capture_records(FIXTURE_CAPTURE_DIR)
    assert baseline_records

    baseline_by_endpoint: dict[str, set[str]] = {}
    for _stem, meta, response in baseline_records:
        signature = _schema_signature(meta, response)
        endpoint = str(signature["endpoint"])
        baseline_by_endpoint.setdefault(endpoint, set()).add(json.dumps(signature, sort_keys=True))

    if not LOCAL_CAPTURE_DIR.exists():
        pytest.skip("No local capture directory exists; skipping schema drift check.")

    local_records = _collect_capture_records(LOCAL_CAPTURE_DIR)
    assert local_records, "Capture directory exists but has no capture records."

    for stem, meta, response in local_records:
        local_signature = _schema_signature(meta, response)
        endpoint = str(local_signature["endpoint"])
        assert endpoint in baseline_by_endpoint, (
            f"Unknown endpoint in local capture '{stem}': {endpoint}"
        )
        signature_payload = json.dumps(local_signature, sort_keys=True)
        assert signature_payload in baseline_by_endpoint[endpoint], (
            f"Schema drift detected for local capture '{stem}' endpoint '{endpoint}'."
        )


def test_full_downloader_replay_with_fixture_payloads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Replay title and viewer fixtures through loader download orchestration."""
    title_payload = (FIXTURE_CAPTURE_DIR / "0001_title_detailV3_100010.pb").read_bytes()
    viewer_payloads = {
        1000311: (FIXTURE_CAPTURE_DIR / "0002_manga_viewer_1000311.pb").read_bytes(),
        1000312: (FIXTURE_CAPTURE_DIR / "0003_manga_viewer_1000312.pb").read_bytes(),
    }

    class ReplayResponse(ResponseLike):
        """Response double wrapping one captured protobuf payload."""

        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            """Fixture payloads are treated as successful HTTP responses."""

    class ReplaySession(SessionLike):
        """Session double that replays captured protobuf responses by endpoint and ID."""

        def __init__(self) -> None:
            """Initialize mutable headers and no-op transport hooks."""
            self.headers: dict[str, str] = {}

        def mount(self, prefix: str, adapter: object) -> None:
            """Ignore adapter mounts; they are irrelevant for fixture replay."""
            del prefix, adapter

        def get(
            self,
            url: str,
            params: Mapping[str, object] | None = None,
            timeout: tuple[float, float] | None = None,
        ) -> ResponseLike:
            """Return fixture payload bytes matching requested endpoint and identifier."""
            del timeout
            params = params or {}
            if url.endswith("/api/title_detailV3"):
                return ReplayResponse(title_payload)
            if url.endswith("/api/manga_viewer"):
                chapter_id = int(str(params["chapter_id"]))
                return ReplayResponse(viewer_payloads[chapter_id])
            raise AssertionError(f"Unexpected replay URL: {url}")

    class ReplayExporter(ExporterLike):
        """Exporter double recording page writes and emitting output markers."""

        def __init__(self, path: Path) -> None:
            self.path = path
            self.images = 0

        def skip_image(self, index: PageIndex) -> bool:
            del index
            return False

        def add_image(self, image_data: bytes, index: PageIndex) -> None:
            del image_data, index
            self.images += 1

        def close(self) -> None:
            self.path.write_bytes(b"ok")

    class ReplayExporterFactory:
        """Factory double satisfying the runtime exporter-factory protocol."""

        def __init__(self) -> None:
            self.created: list[ReplayExporter] = []

        def __call__(
            self,
            *,
            title: TitleLike,
            chapter: ChapterLike,
            next_chapter: ChapterLike | None = None,
        ) -> ExporterLike:
            del title, next_chapter
            exporter = ReplayExporter(tmp_path / f"{chapter.chapter_id}.cbz")
            self.created.append(exporter)
            return exporter

    exporter_factory = ReplayExporterFactory()

    loader = MangaLoader(
        exporter=exporter_factory,
        quality="high",
        split=False,
        meta=False,
        destination=str(tmp_path),
        output_format="cbz",
        session=ReplaySession(),
    )
    monkeypatch.setattr(
        loader._runtime.services.page_image_service,
        "fetch_page_image",
        lambda _page, *, download_image, decrypt_image: b"img",
    )

    summary = loader.download(
        title_ids=None,
        chapter_ids={1000311, 1000312},
        min_chapter=0,
        max_chapter=999,
        last_chapter=False,
    )

    assert summary.downloaded == 2
    assert summary.failed == 0
    assert len(exporter_factory.created) == 2
    assert all(exporter.images > 10 for exporter in exporter_factory.created)
