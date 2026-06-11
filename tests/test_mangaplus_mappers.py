"""Replay tests for MangaPlus protobuf-to-domain mappers."""

from __future__ import annotations

from pathlib import Path

from mloader.domain.planning import DownloadPlan, TitleDownloadPlan
from mloader.infrastructure.mangaplus import mappers
from mloader.infrastructure.mangaplus import parsing
from mloader.manga_loader.chapter_planning import ChapterPlanner
from mloader.response_pb2 import Response

FIXTURE_CAPTURE_DIR = Path(__file__).parent / "fixtures" / "api_captures" / "baseline"


def test_title_detail_mapper_matches_fixture_chapter_planning() -> None:
    """Verify title-detail DTOs preserve fixture data used by existing chapter planning."""
    raw_payload = (FIXTURE_CAPTURE_DIR / "0001_title_detailV3_100010.pb").read_bytes()
    parsed = Response.FromString(raw_payload)
    title_detail_proto = parsed.success.title_detail_view
    mapped = parsing.parse_title_detail_response(raw_payload)
    existing_chapter_data = ChapterPlanner.extract_chapter_data(mapped, lambda value: value)

    assert mapped.title.title_id == title_detail_proto.title.title_id == 100010
    assert mapped.title.name == title_detail_proto.title.name == "Dr. STONE"
    assert len(mapped.chapters) == len(existing_chapter_data) == 236
    assert {chapter.chapter_id for chapter in mapped.chapters} == set(existing_chapter_data)


def test_title_detail_mapper_preserves_comicinfo_metadata() -> None:
    """Verify title-detail metadata needed for ComicInfo is mapped onto titles."""
    response = Response()
    title_detail = response.success.title_detail_view
    title_detail.title.title_id = 100312
    title_detail.title.name = "Test"
    title_detail.title.author = "Writer & Artist"
    title_detail.overview = "Summary <with> detail"
    title_detail.sns.url = "https://jumpg-webapi.tokyo-cdn.com/www/sns_share?title_id=100312"
    first_tag = title_detail.tags.add()
    first_tag.name = "Action & Adventure"
    first_tag.slug = "action-adventure"
    second_tag = title_detail.tags.add()
    second_tag.name = "Sci-Fi / Fantasy"
    second_tag.slug = "sci-fi-fantasy"
    chapter = title_detail.chapter_list.add()
    chapter.title_id = 100312
    chapter.chapter_id = 1024959
    chapter.name = "#001"

    mapped = mappers.title_detail_from_proto(title_detail)

    assert mapped.overview == "Summary <with> detail"
    assert mapped.title.author == "Writer & Artist"
    assert mapped.title.overview == "Summary <with> detail"
    assert (
        mapped.title.web_url == "https://jumpg-webapi.tokyo-cdn.com/www/sns_share?title_id=100312"
    )
    assert [(tag.name, tag.slug) for tag in mapped.title.tags] == [
        ("Action & Adventure", "action-adventure"),
        ("Sci-Fi / Fantasy", "sci-fi-fantasy"),
    ]


def test_manga_viewer_mapper_matches_fixture_viewer_payload() -> None:
    """Verify manga-viewer DTOs preserve fixture chapter and page identities."""
    raw_payload = (FIXTURE_CAPTURE_DIR / "0002_manga_viewer_1000311.pb").read_bytes()
    parsed = Response.FromString(raw_payload)
    viewer_proto = parsed.success.manga_viewer
    mapped = parsing.parse_manga_viewer_response(raw_payload)

    assert mapped.title_id == viewer_proto.title_id == 100010
    assert mapped.chapter_id == viewer_proto.chapter_id == 1000311
    assert mapped.chapter_name == viewer_proto.chapter_name
    assert [chapter.chapter_id for chapter in mapped.chapters] == [
        chapter.chapter_id for chapter in viewer_proto.chapters
    ]
    assert len(mapped.downloadable_pages) == len(
        [page for page in viewer_proto.pages if page.manga_page.image_url]
    )
    assert mapped.last_page is not None
    assert mapped.last_page.current_chapter.chapter_id == viewer_proto.chapter_id


def test_mapper_handles_terminal_page_without_next_chapter() -> None:
    """Verify mapper represents absent next-chapter and non-image pages explicitly."""
    response = Response()
    viewer = response.success.manga_viewer
    viewer.title_id = 100010
    viewer.chapter_id = 1000311
    viewer.title_name = "Dr. STONE"
    viewer.chapter_name = "#001"
    viewer_chapter = viewer.chapters.add()
    viewer_chapter.title_id = 100010
    viewer_chapter.chapter_id = 1000311
    viewer_chapter.name = "#001"
    viewer_page = viewer.pages.add()
    viewer_page.last_page.current_chapter.title_id = 100010
    viewer_page.last_page.current_chapter.chapter_id = 1000311
    viewer_page.last_page.current_chapter.name = "#001"

    mapped = mappers.manga_viewer_from_proto(viewer)

    assert mapped.downloadable_pages == ()
    assert mapped.pages[0].manga_page is None
    assert mapped.pages[0].last_page is not None
    assert mapped.pages[0].last_page.next_chapter is None


def test_titles_from_all_titles_proto_flattens_title_groups() -> None:
    """Verify title-index mapper returns stable title DTOs."""
    response = Response()
    group = response.success.all_titles_view.title_groups.add()
    first = group.titles.add()
    first.title_id = 100001
    first.name = "First"
    first.author = "Author A"
    second = group.titles.add()
    second.title_id = 100002
    second.name = "Second"
    second.author = "Author B"

    titles = mappers.titles_from_all_titles_proto(response.success.all_titles_view)

    assert [title.title_id for title in titles] == [100001, 100002]
    assert [title.name for title in titles] == ["First", "Second"]


def test_download_plan_can_be_built_from_replayed_fixture_selection() -> None:
    """Verify fixture-derived selections can be represented as a stable domain plan."""
    raw_payload = (FIXTURE_CAPTURE_DIR / "0001_title_detailV3_100010.pb").read_bytes()
    mapped = parsing.parse_title_detail_response(raw_payload)
    selected_chapters = mapped.chapters[:2]

    plan = DownloadPlan(
        title_plans=(TitleDownloadPlan(title_detail=mapped, selected_chapters=selected_chapters),)
    )

    assert plan.title_count == 1
    assert plan.chapter_count == 2
    assert plan.selections[0].title_id == 100010
    assert plan.selections[0].chapter_ids == frozenset(
        chapter.chapter_id for chapter in selected_chapters
    )
