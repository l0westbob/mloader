"""Tests for stable MangaPlus domain DTOs."""

from __future__ import annotations

import pytest

from mloader.domain.manga import Chapter, ChapterGroup, LastPage, MangaPage, MangaViewer, Title
from mloader.domain.manga import TitleDetail, ViewerPage
from mloader.domain.planning import ChapterSelection, DownloadPlan, TitleDownloadPlan
from mloader.domain.planning import build_download_plan


def _chapter(chapter_id: int, name: str) -> Chapter:
    """Build a minimal chapter DTO for domain model tests."""
    return Chapter(
        title_id=100010,
        chapter_id=chapter_id,
        name=name,
        sub_title=f"Chapter {chapter_id}",
        thumbnail_url="https://img.example/thumb.webp",
    )


def test_title_detail_chapters_flattens_all_groups_in_display_order() -> None:
    """Verify title detail exposes all grouped chapters in MangaPlus order."""
    first = _chapter(1, "#001")
    middle = _chapter(2, "#002")
    last = _chapter(3, "#003")
    detail = TitleDetail(
        title=Title(
            title_id=100010,
            name="Dr. STONE",
            author="Riichiro Inagaki / Boichi",
            portrait_image_url="https://img.example/portrait.webp",
            landscape_image_url="https://img.example/landscape.webp",
            language=0,
        ),
        title_image_url="https://img.example/main.webp",
        overview="Science adventure.",
        non_appearance_info="",
        number_of_views=123,
        chapter_groups=(
            ChapterGroup(
                first_chapters=(first,),
                mid_chapters=(middle,),
                last_chapters=(last,),
            ),
        ),
    )

    assert detail.chapter_groups[0].chapters == (first, middle, last)
    assert detail.chapters == (first, middle, last)


def test_manga_viewer_downloadable_pages_filters_non_image_pages() -> None:
    """Verify viewer DTO exposes only page records with image URLs."""
    image_page = MangaPage(
        image_url="https://img.example/page.jpg",
        width=1200,
        height=1800,
        page_type=0,
        encryption_key="",
    )
    viewer = MangaViewer(
        title_id=100010,
        chapter_id=1000311,
        title_name="Dr. STONE",
        chapter_name="#001",
        chapters=(_chapter(1000311, "#001"),),
        pages=(
            ViewerPage(manga_page=image_page, last_page=None),
            ViewerPage(manga_page=None, last_page=None),
        ),
    )

    assert viewer.downloadable_pages == (image_page,)


def test_manga_viewer_last_page_returns_terminal_metadata() -> None:
    """Verify viewer DTO exposes terminal metadata without probing page envelopes."""
    chapter = _chapter(1000311, "#001")
    last_page = LastPage(current_chapter=chapter, next_chapter=None)
    viewer = MangaViewer(
        title_id=100010,
        chapter_id=1000311,
        title_name="Dr. STONE",
        chapter_name="#001",
        chapters=(chapter,),
        pages=(
            ViewerPage(manga_page=None, last_page=None),
            ViewerPage(manga_page=None, last_page=last_page),
        ),
    )

    assert viewer.last_page is last_page


def test_manga_viewer_last_page_returns_none_without_terminal_metadata() -> None:
    """Verify viewer DTO reports missing terminal metadata directly."""
    viewer = MangaViewer(
        title_id=100010,
        chapter_id=1000311,
        title_name="Dr. STONE",
        chapter_name="#001",
        chapters=(_chapter(1000311, "#001"),),
        pages=(ViewerPage(manga_page=None, last_page=None),),
    )

    assert viewer.last_page is None


def test_download_plan_counts_concrete_title_plans() -> None:
    """Verify concrete title plans expose stable selection summaries."""
    first_detail = TitleDetail(
        title=Title(
            title_id=100010,
            name="One",
            author="A",
            portrait_image_url="",
            landscape_image_url="",
            language=0,
        ),
        title_image_url="",
        overview="",
        non_appearance_info="",
        number_of_views=0,
        chapter_groups=(
            ChapterGroup(
                first_chapters=(_chapter(1, "#001"), _chapter(2, "#002")),
                mid_chapters=(),
                last_chapters=(),
            ),
        ),
    )
    second_detail = TitleDetail(
        title=Title(
            title_id=100020,
            name="Two",
            author="B",
            portrait_image_url="",
            landscape_image_url="",
            language=0,
        ),
        title_image_url="",
        overview="",
        non_appearance_info="",
        number_of_views=0,
        chapter_groups=(
            ChapterGroup(first_chapters=(_chapter(3, "#003"),), mid_chapters=(), last_chapters=()),
        ),
    )
    plan = DownloadPlan(
        title_plans=(
            TitleDownloadPlan(title_detail=first_detail, selected_chapters=first_detail.chapters),
            TitleDownloadPlan(title_detail=second_detail, selected_chapters=second_detail.chapters),
        )
    )

    assert [selection.title_id for selection in plan.selections] == [100010, 100020]
    assert plan.selections[0].chapter_ids == frozenset({1, 2})
    assert plan.title_count == 2
    assert plan.chapter_count == 3
    assert plan.selections[0].chapter_count == 2


def test_chapter_selection_counts_selected_ids() -> None:
    """Verify ID-only selection summaries expose chapter counts."""
    selection = ChapterSelection(title_id=100010, chapter_ids=frozenset({1, 2, 3}))

    assert selection.chapter_count == 3


def test_build_download_plan_requires_at_least_one_target() -> None:
    """Verify planning rejects empty target inputs."""
    with pytest.raises(ValueError, match="Expected at least one title or chapter id"):
        build_download_plan(
            title_ids=None,
            chapter_numbers=None,
            chapter_ids=None,
            min_chapter=0,
            max_chapter=999,
            last_chapter=False,
            load_title_detail=lambda _title_id: _title_detail_with_chapters([]),
            load_viewer=lambda _chapter_id: MangaViewer(
                title_id=0,
                chapter_id=0,
                title_name="",
                chapter_name="",
                chapters=(),
                pages=(),
            ),
        )


def _title_detail_with_chapters(chapters: list[Chapter]) -> TitleDetail:
    """Build a minimal title detail containing ``chapters``."""
    return TitleDetail(
        title=Title(
            title_id=100010,
            name="Dr. STONE",
            author="A",
            portrait_image_url="",
            landscape_image_url="",
            language=0,
        ),
        title_image_url="",
        overview="",
        non_appearance_info="",
        number_of_views=0,
        chapter_groups=(
            ChapterGroup(first_chapters=tuple(chapters), mid_chapters=(), last_chapters=()),
        ),
    )


def test_build_download_plan_rejects_chapter_numbers_without_title_context() -> None:
    """Verify chapter numbers require a title or direct viewer context."""
    with pytest.raises(ValueError, match="Chapter numbers require"):
        build_download_plan(
            title_ids=None,
            chapter_numbers={1},
            chapter_ids=None,
            min_chapter=0,
            max_chapter=999,
            last_chapter=False,
            load_title_detail=lambda _title_id: _title_detail_with_chapters([]),
            load_viewer=lambda _chapter_id: MangaViewer(
                title_id=0,
                chapter_id=0,
                title_name="",
                chapter_name="",
                chapters=(),
                pages=(),
            ),
        )


def test_build_download_plan_last_chapter_selects_final_candidate() -> None:
    """Verify last-chapter mode selects only the final candidate chapter."""
    first = _chapter(1000311, "#001")
    last = _chapter(1000312, "#002")
    detail = _title_detail_with_chapters([first, last])

    plan = build_download_plan(
        title_ids={100010},
        chapter_numbers=None,
        chapter_ids=None,
        min_chapter=0,
        max_chapter=999,
        last_chapter=True,
        load_title_detail=lambda _title_id: detail,
        load_viewer=lambda _chapter_id: MangaViewer(
            title_id=0,
            chapter_id=0,
            title_name="",
            chapter_name="",
            chapters=(),
            pages=(),
        ),
    )

    assert plan.title_plans[0].selected_chapters == (last,)


def test_build_download_plan_uses_viewer_last_page_fallback_for_direct_chapter() -> None:
    """Verify direct chapter IDs can be planned from viewer terminal metadata."""
    chapter = _chapter(1000311, "#001")
    title_detail = TitleDetail(
        title=Title(
            title_id=100010,
            name="Dr. STONE",
            author="A",
            portrait_image_url="",
            landscape_image_url="",
            language=0,
        ),
        title_image_url="",
        overview="",
        non_appearance_info="",
        number_of_views=0,
        chapter_groups=(ChapterGroup(first_chapters=(), mid_chapters=(), last_chapters=()),),
    )
    viewer = MangaViewer(
        title_id=100010,
        chapter_id=1000311,
        title_name="Dr. STONE",
        chapter_name="#001",
        chapters=(),
        pages=(ViewerPage(manga_page=None, last_page=LastPage(chapter, None)),),
    )

    plan = build_download_plan(
        title_ids=None,
        chapter_numbers=None,
        chapter_ids={1000311},
        min_chapter=0,
        max_chapter=999,
        last_chapter=False,
        load_title_detail=lambda _title_id: title_detail,
        load_viewer=lambda _chapter_id: viewer,
    )

    assert plan.title_plans[0].selected_chapters == (chapter,)


def test_build_download_plan_synthesizes_direct_chapter_without_viewer_chapters() -> None:
    """Verify direct chapter planning has a minimal fallback when viewer metadata is sparse."""
    title_detail = TitleDetail(
        title=Title(
            title_id=100010,
            name="Dr. STONE",
            author="A",
            portrait_image_url="",
            landscape_image_url="",
            language=0,
        ),
        title_image_url="",
        overview="",
        non_appearance_info="",
        number_of_views=0,
        chapter_groups=(ChapterGroup(first_chapters=(), mid_chapters=(), last_chapters=()),),
    )
    viewer = MangaViewer(
        title_id=100010,
        chapter_id=1000311,
        title_name="Dr. STONE",
        chapter_name="#001",
        chapters=(),
        pages=(),
    )

    plan = build_download_plan(
        title_ids=None,
        chapter_numbers=None,
        chapter_ids={1000311},
        min_chapter=0,
        max_chapter=999,
        last_chapter=False,
        load_title_detail=lambda _title_id: title_detail,
        load_viewer=lambda _chapter_id: viewer,
    )

    selected = plan.title_plans[0].selected_chapters[0]
    assert selected.chapter_id == 1000311
    assert selected.name == "#001"


def test_build_download_plan_uses_matching_viewer_chapter_as_current_fallback() -> None:
    """Verify direct chapter planning uses viewer chapter lists when terminal metadata is absent."""
    current = _chapter(1000311, "#001")
    other = _chapter(1000312, "#002")
    title_detail = _title_detail_with_chapters([])
    viewer = MangaViewer(
        title_id=100010,
        chapter_id=1000311,
        title_name="Dr. STONE",
        chapter_name="#001",
        chapters=(other, current),
        pages=(),
    )

    plan = build_download_plan(
        title_ids=None,
        chapter_numbers=None,
        chapter_ids={1000311},
        min_chapter=0,
        max_chapter=999,
        last_chapter=False,
        load_title_detail=lambda _title_id: title_detail,
        load_viewer=lambda _chapter_id: viewer,
    )

    assert plan.title_plans[0].selected_chapters == (current,)


def test_build_download_plan_reuses_title_details_loaded_during_selection() -> None:
    """Verify title detail payloads loaded for selection are not loaded again."""
    chapter = _chapter(1000311, "#001")
    title_detail = TitleDetail(
        title=Title(
            title_id=100010,
            name="Dr. STONE",
            author="A",
            portrait_image_url="",
            landscape_image_url="",
            language=0,
        ),
        title_image_url="",
        overview="",
        non_appearance_info="",
        number_of_views=0,
        chapter_groups=(
            ChapterGroup(first_chapters=(chapter,), mid_chapters=(), last_chapters=()),
        ),
    )
    calls: list[int] = []

    def load_title_detail(title_id: int) -> TitleDetail:
        calls.append(title_id)
        return title_detail

    plan = build_download_plan(
        title_ids={100010},
        chapter_numbers=None,
        chapter_ids=None,
        min_chapter=0,
        max_chapter=999,
        last_chapter=False,
        load_title_detail=load_title_detail,
        load_viewer=lambda _chapter_id: MangaViewer(
            title_id=0,
            chapter_id=0,
            title_name="",
            chapter_name="",
            chapters=(),
            pages=(),
        ),
    )

    assert calls == [100010]
    assert plan.title_plans[0].selected_chapters == (chapter,)
