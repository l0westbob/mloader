"""Tests for immutable domain request models."""

from __future__ import annotations

from mloader.domain.requests import DownloadRequest, MAX_CHAPTER_ID


def _build_request(*, end: int | None = None) -> DownloadRequest:
    """Create a baseline download request for domain model tests."""
    return DownloadRequest(
        out_dir="/tmp",
        raw=False,
        output_format="cbz",
        capture_api_dir=None,
        quality="super_high",
        split=False,
        begin=0,
        end=end,
        last=False,
        chapter_title=False,
        chapter_subdir=False,
        meta=False,
        resume=True,
        manifest_reset=False,
        chapters=frozenset(),
        chapter_ids=frozenset(),
        titles=frozenset(),
    )


def test_download_request_max_chapter_defaults_to_domain_limit() -> None:
    """Verify unset max bound resolves to the domain-level fallback limit."""
    request = _build_request(end=None)

    assert request.max_chapter == MAX_CHAPTER_ID


def test_download_request_max_chapter_uses_explicit_end_bound() -> None:
    """Verify explicit chapter end bound is preserved as max chapter."""
    request = _build_request(end=42)

    assert request.max_chapter == 42


def test_download_request_with_additional_titles_merges_and_deduplicates() -> None:
    """Verify helper returns a new request with merged title IDs."""
    request = _build_request(end=42).with_additional_titles({100001, 100002})
    merged = request.with_additional_titles({100002, 100003})

    assert request.titles == frozenset({100001, 100002})
    assert merged.titles == frozenset({100001, 100002, 100003})


def test_download_request_has_targets_reflects_titles_or_chapters() -> None:
    """Verify target presence flag is true when either target bucket is populated."""
    assert _build_request().has_targets is False
    assert _build_request().with_additional_titles({1}).has_targets is True

    chapters_only = DownloadRequest(
        out_dir="/tmp",
        raw=False,
        output_format="cbz",
        capture_api_dir=None,
        quality="super_high",
        split=False,
        begin=0,
        end=None,
        last=False,
        chapter_title=False,
        chapter_subdir=False,
        meta=False,
        resume=True,
        manifest_reset=False,
        chapters=frozenset({77}),
        chapter_ids=frozenset(),
        titles=frozenset(),
    )

    assert chapters_only.has_targets is True
