"""Direct payload verifier tests for MangaPlus capture verification."""

from __future__ import annotations

import pytest

from mloader.infrastructure.mangaplus.capture_metadata import CaptureVerificationError
from mloader.infrastructure.mangaplus.capture_payload_validation import (
    verify_manga_viewer_payload,
    verify_title_detail_payload,
    verify_title_index_payload,
)
from mloader.response_pb2 import Response


def test_verify_title_detail_payload_rejects_missing_title_detail() -> None:
    """Verify title-detail payload verifier rejects missing payload branch."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    parsed.success.manga_viewer.chapter_id = 1024959
    with pytest.raises(CaptureVerificationError, match="Missing success.title_detail_view"):
        verify_title_detail_payload(parsed, "sample")


def test_verify_title_detail_payload_rejects_missing_title_identity() -> None:
    """Verify title-detail payload verifier requires title identity fields."""
    parsed = Response()
    parsed.success.title_detail_view.chapter_list_group.add()
    with pytest.raises(CaptureVerificationError, match="Missing required title identity fields"):
        verify_title_detail_payload(parsed, "sample")


def test_verify_title_detail_payload_rejects_empty_chapter_groups() -> None:
    """Verify title-detail payload verifier rejects groups without chapters."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100312
    parsed.success.title_detail_view.title.name = "T"
    parsed.success.title_detail_view.chapter_list_group.add()
    with pytest.raises(
        CaptureVerificationError, match="No chapter entries found in chapter_list_group"
    ):
        verify_title_detail_payload(parsed, "sample")


def test_verify_title_detail_payload_accepts_flat_mobile_chapter_list() -> None:
    """Verify title-detail verifier accepts the mobile flat chapter list shape."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100312
    parsed.success.title_detail_view.title.name = "T"
    parsed.success.title_detail_view.chapter_list.add().chapter_id = 1024959

    verify_title_detail_payload(parsed, "sample")


def test_verify_title_index_payload_rejects_missing_title_index() -> None:
    """Verify title-index verifier rejects missing all_titles_view branch."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    with pytest.raises(CaptureVerificationError, match="Missing success.all_titles_view"):
        verify_title_index_payload(parsed, "sample")


def test_verify_title_index_payload_rejects_empty_groups() -> None:
    """Verify title-index verifier requires at least one group."""
    parsed = Response()
    parsed.success.all_titles_view.SetInParent()
    with pytest.raises(CaptureVerificationError, match="No title_groups records"):
        verify_title_index_payload(parsed, "sample")


def test_verify_title_index_payload_rejects_groups_without_titles() -> None:
    """Verify title-index verifier requires at least one title entry."""
    parsed = Response()
    parsed.success.all_titles_view.title_groups.add().group_name = "empty"
    with pytest.raises(CaptureVerificationError, match="No title records found"):
        verify_title_index_payload(parsed, "sample")


def test_verify_manga_viewer_payload_rejects_missing_viewer() -> None:
    """Verify manga-viewer payload verifier rejects missing payload branch."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100312
    parsed.success.title_detail_view.title.name = "T"
    with pytest.raises(CaptureVerificationError, match="Missing success.manga_viewer"):
        verify_manga_viewer_payload(parsed, "sample")


def test_verify_manga_viewer_payload_rejects_missing_ids() -> None:
    """Verify manga-viewer payload verifier requires non-zero identity fields."""
    parsed = Response()
    parsed.success.manga_viewer.pages.add().manga_page.image_url = "http://img"
    with pytest.raises(CaptureVerificationError, match="Missing viewer title_id/chapter_id fields"):
        verify_manga_viewer_payload(parsed, "sample")


def test_verify_manga_viewer_payload_rejects_missing_image_urls() -> None:
    """Verify manga-viewer payload verifier requires at least one image URL."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    parsed.success.manga_viewer.chapter_id = 1024959
    parsed.success.manga_viewer.pages.add()
    with pytest.raises(CaptureVerificationError, match="No manga_page.image_url found in pages"):
        verify_manga_viewer_payload(parsed, "sample")


def test_verify_manga_viewer_payload_accepts_declared_subscription_required() -> None:
    """Verify subscription-required viewer captures can be stored as baseline records."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    parsed.success.manga_viewer.chapter_id = 1024959

    verify_manga_viewer_payload(
        parsed,
        "sample",
        metadata={"expected_runtime_error": "subscription_required"},
    )


def test_verify_manga_viewer_payload_rejects_missing_last_page_chapter() -> None:
    """Verify manga-viewer payload verifier requires terminal chapter linkage."""
    parsed = Response()
    parsed.success.manga_viewer.title_id = 100312
    parsed.success.manga_viewer.chapter_id = 1024959
    page = parsed.success.manga_viewer.pages.add()
    page.manga_page.image_url = "http://img"
    with pytest.raises(CaptureVerificationError, match="Missing last_page.current_chapter"):
        verify_manga_viewer_payload(parsed, "sample")
