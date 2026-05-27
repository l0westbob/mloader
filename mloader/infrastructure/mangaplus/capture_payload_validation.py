"""Runtime-field validation for captured MangaPlus protobuf payloads."""

from __future__ import annotations

from typing import Any

from mloader.infrastructure.mangaplus.capture_metadata import CaptureVerificationError
from mloader.response_pb2 import Response


def verify_title_detail_payload(parsed: Response, stem: str) -> None:
    """Validate required title-detail fields used by planner/download flow."""
    if not parsed.success.HasField("title_detail_view"):
        raise CaptureVerificationError(f"Missing success.title_detail_view in {stem}.pb")

    title_detail = parsed.success.title_detail_view
    if title_detail.title.title_id == 0 or not title_detail.title.name:
        raise CaptureVerificationError(f"Missing required title identity fields in {stem}.pb")

    has_grouped_chapter = any(
        group.first_chapter_list or group.mid_chapter_list or group.last_chapter_list
        for group in title_detail.chapter_list_group
    )
    if has_grouped_chapter or title_detail.chapter_list:
        return

    if not title_detail.chapter_list_group:
        raise CaptureVerificationError(
            f"No chapter_list_group records or flat chapter_list records in {stem}.pb"
        )

    if not has_grouped_chapter:
        raise CaptureVerificationError(
            f"No chapter entries found in chapter_list_group for {stem}.pb"
        )


def verify_manga_viewer_payload(
    parsed: Response,
    stem: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Validate required manga-viewer fields used by download flow."""
    if not parsed.success.HasField("manga_viewer"):
        raise CaptureVerificationError(f"Missing success.manga_viewer in {stem}.pb")

    viewer = parsed.success.manga_viewer
    if viewer.title_id == 0 or viewer.chapter_id == 0:
        raise CaptureVerificationError(f"Missing viewer title_id/chapter_id fields in {stem}.pb")

    if not viewer.pages:
        metadata = metadata or {}
        if metadata.get("expected_runtime_error") == "subscription_required":
            return
        raise CaptureVerificationError(f"No pages found in manga_viewer payload {stem}.pb")

    if not any(page.manga_page.image_url for page in viewer.pages):
        raise CaptureVerificationError(f"No manga_page.image_url found in pages for {stem}.pb")

    last_page = viewer.pages[-1].last_page
    if last_page.current_chapter.chapter_id == 0:
        raise CaptureVerificationError(f"Missing last_page.current_chapter in {stem}.pb")


def verify_title_index_payload(parsed: Response, stem: str) -> None:
    """Validate required title-index fields used by ``--all`` discovery."""
    if not parsed.success.HasField("all_titles_view"):
        raise CaptureVerificationError(f"Missing success.all_titles_view in {stem}.pb")

    all_titles = parsed.success.all_titles_view
    if not all_titles.title_groups:
        raise CaptureVerificationError(f"No title_groups records in {stem}.pb")

    if not any(group.titles for group in all_titles.title_groups):
        raise CaptureVerificationError(f"No title records found in title_groups for {stem}.pb")
