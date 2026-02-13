"""Replay tests using real captured API payload fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from mloader.manga_loader import api
from mloader.manga_loader.services import ChapterPlanner
from mloader.utils import escape_path

FIXTURE_CAPTURE_DIR = Path(__file__).parent / "fixtures" / "api_captures" / "baseline"
LOCAL_CAPTURE_DIR = Path("capture")


def _as_dict(value: object, context: str) -> dict[str, Any]:
    """Return ``value`` as a dictionary or raise a descriptive assertion error."""
    if not isinstance(value, dict):
        raise AssertionError(f"Expected dict for {context}, got {type(value).__name__}")
    return value


def _as_list(value: object, context: str) -> list[Any]:
    """Return ``value`` as a list or raise a descriptive assertion error."""
    if not isinstance(value, list):
        raise AssertionError(f"Expected list for {context}, got {type(value).__name__}")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    """Load and return JSON object from ``path``."""
    return _as_dict(json.loads(path.read_text(encoding="utf-8")), str(path))


def _collect_capture_records(capture_dir: Path) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Collect capture metadata/response records from ``capture_dir``."""
    records: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for meta_path in sorted(capture_dir.glob("*.meta.json")):
        stem = meta_path.name.removesuffix(".meta.json")
        response_path = capture_dir / f"{stem}.response.json"
        if not response_path.exists():
            raise AssertionError(f"Missing response JSON for capture stem: {stem}")
        records.append((stem, _load_json(meta_path), _load_json(response_path)))
    return records


def _schema_signature(meta: dict[str, Any], response: dict[str, Any]) -> dict[str, object]:
    """Build a schema signature from capture metadata and parsed response JSON."""
    endpoint = str(meta["endpoint"])
    success = _as_dict(response["success"], "response.success")
    signature: dict[str, object] = {
        "endpoint": endpoint,
        "url_path": urlparse(str(meta["url"])).path,
        "meta_keys": sorted(meta.keys()),
        "param_keys": sorted(_as_dict(meta["params"], "meta.params").keys()),
        "success_keys": sorted(success.keys()),
    }

    if endpoint == "manga_viewer":
        viewer = _as_dict(success["manga_viewer"], "response.success.manga_viewer")
        signature["payload_keys"] = sorted(viewer.keys())

        pages = _as_list(viewer["pages"], "response.success.manga_viewer.pages")
        first_page = _as_dict(pages[0], "response.success.manga_viewer.pages[0]")
        last_page = _as_dict(pages[-1], "response.success.manga_viewer.pages[-1]")
        signature["first_page_keys"] = sorted(first_page.keys())
        signature["last_page_keys"] = sorted(last_page.keys())
        signature["manga_page_keys"] = sorted(
            _as_dict(first_page["manga_page"], "response.success.manga_viewer.pages[0].manga_page").keys()
        )
        signature["last_page_payload_keys"] = sorted(
            _as_dict(last_page["last_page"], "response.success.manga_viewer.pages[-1].last_page").keys()
        )
        return signature

    if endpoint == "title_detailV3":
        title_detail = _as_dict(success["title_detail_view"], "response.success.title_detail_view")
        signature["payload_keys"] = sorted(title_detail.keys())
        signature["title_keys"] = sorted(
            _as_dict(title_detail["title"], "response.success.title_detail_view.title").keys()
        )

        chapter_groups = _as_list(
            title_detail["chapter_list_group"],
            "response.success.title_detail_view.chapter_list_group",
        )
        first_group = _as_dict(
            chapter_groups[0],
            "response.success.title_detail_view.chapter_list_group[0]",
        )
        signature["chapter_group_keys"] = sorted(first_group.keys())

        first_chapter_list = _as_list(first_group["first_chapter_list"], "chapter_group.first_chapter_list")
        first_chapter = _as_dict(first_chapter_list[0], "chapter_group.first_chapter_list[0]")
        signature["chapter_keys"] = sorted(first_chapter.keys())
        return signature

    raise AssertionError(f"Unexpected endpoint in capture metadata: {endpoint}")


def test_title_detail_fixture_replays_into_chapter_planner() -> None:
    """Validate chapter planning logic against a real captured title-detail payload."""
    raw_payload = (FIXTURE_CAPTURE_DIR / "0001_title_detailV3_100010.pb").read_bytes()
    title_dump = api._parse_title_detail_response(raw_payload)

    assert title_dump.title.title_id == 100010
    assert title_dump.title.name == "Dr. STONE"

    chapter_data = ChapterPlanner.extract_chapter_data(title_dump, lambda value: value)
    assert len(chapter_data) == 236

    chapter_2 = ChapterPlanner.find_chapter_by_id(title_dump, 1000311)
    assert chapter_2 is not None
    expected_existing = ChapterPlanner.build_expected_filename(
        escape_path(title_dump.title.name).title(),
        chapter_2,
        chapter_2.sub_title,
    )

    result = ChapterPlanner.filter_chapters_to_download(
        chapter_data=chapter_data,
        title_dump=title_dump,
        title_detail=title_dump.title,
        existing_files=[expected_existing],
        requested_chapter_ids={1000311, 1000312},
    )
    assert result == [1000312]


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
    viewer = api._parse_manga_viewer_response(raw_payload)

    assert viewer.title_id == 100010
    assert viewer.chapter_id == chapter_id
    assert len(viewer.pages) > 20
    assert len(viewer.chapters) == 3

    last_page = viewer.pages[-1].last_page
    assert last_page.current_chapter.chapter_id == chapter_id
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
        assert endpoint in baseline_by_endpoint, f"Unknown endpoint in local capture '{stem}': {endpoint}"
        signature_payload = json.dumps(local_signature, sort_keys=True)
        assert signature_payload in baseline_by_endpoint[endpoint], (
            f"Schema drift detected for local capture '{stem}' endpoint '{endpoint}'."
        )
