"""Schema-signature helper tests for capture verification."""

from __future__ import annotations

import json

import pytest

from mloader.infrastructure.mangaplus.api_response import ApiPayloadClassification
from mloader.infrastructure.mangaplus.capture_metadata import CaptureVerificationError
from mloader.infrastructure.mangaplus.capture_signatures import (
    as_dict,
    as_list,
    build_api_error_signature,
    build_schema_signature,
)
from mloader.response_pb2 import Response


def test_build_api_error_signature_requires_error_details() -> None:
    """Verify malformed internal classifications fail with a clear message."""
    with pytest.raises(CaptureVerificationError, match="Expected API error details"):
        build_api_error_signature(
            endpoint="title_index",
            metadata={"params": {}},
            classification=ApiPayloadClassification(kind="api_error"),
        )


def test_build_schema_signature_rejects_unknown_endpoint() -> None:
    """Verify schema-signature builder rejects unsupported endpoint names."""
    parsed = Response()
    parsed.success.title_detail_view.title.title_id = 100312
    parsed.success.title_detail_view.title.name = "title"
    group = parsed.success.title_detail_view.chapter_list_group.add()
    group.first_chapter_list.add().chapter_id = 1024959
    with pytest.raises(CaptureVerificationError, match="Unsupported endpoint"):
        build_schema_signature(
            endpoint="unknown",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=parsed,
        )


def test_as_dict_rejects_non_dict() -> None:
    """Verify dict coercion helper rejects non-object values."""
    with pytest.raises(CaptureVerificationError, match="Expected object at"):
        as_dict([], "ctx")


def test_as_list_rejects_non_list() -> None:
    """Verify list coercion helper rejects non-list values."""
    with pytest.raises(CaptureVerificationError, match="Expected list at"):
        as_list({}, "ctx")


def test_build_schema_signature_rejects_empty_pages_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects manga_viewer payloads with explicit empty pages list."""
    monkeypatch.setattr(
        "mloader.infrastructure.mangaplus.capture_signatures.MessageToDict",
        lambda *_args, **_kwargs: {"success": {"manga_viewer": {"pages": []}}},
    )

    with pytest.raises(CaptureVerificationError, match="Expected at least one page"):
        build_schema_signature(
            endpoint="manga_viewer",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=Response(),
        )


def test_build_schema_signature_accepts_subscription_required_manga_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signatures can describe subscription-required viewer payloads."""
    monkeypatch.setattr(
        "mloader.infrastructure.mangaplus.capture_signatures.MessageToDict",
        lambda *_args, **_kwargs: {"success": {"manga_viewer": {"pages": []}}},
    )

    signature = json.loads(
        build_schema_signature(
            endpoint="manga_viewer",
            metadata={
                "expected_runtime_error": "subscription_required",
                "params": {},
                "url": "https://example.invalid/api/manga_viewer",
            },
            parsed=Response(),
        )
    )

    assert signature["payload_state"] == "subscription_required"


def test_build_schema_signature_rejects_empty_title_index_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects title-index payloads with no groups."""
    monkeypatch.setattr(
        "mloader.infrastructure.mangaplus.capture_signatures.MessageToDict",
        lambda *_args, **_kwargs: {"success": {"all_titles_view": {"title_groups": []}}},
    )

    with pytest.raises(CaptureVerificationError, match="Expected at least one group"):
        build_schema_signature(
            endpoint="title_index",
            metadata={"params": {}, "url": "https://example.invalid/api/title_list/allV2"},
            parsed=Response(),
        )


def test_build_schema_signature_rejects_title_index_groups_without_titles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects title-index groups with no titles."""
    monkeypatch.setattr(
        "mloader.infrastructure.mangaplus.capture_signatures.MessageToDict",
        lambda *_args, **_kwargs: {
            "success": {"all_titles_view": {"title_groups": [{"titles": []}]}}
        },
    )

    with pytest.raises(CaptureVerificationError, match="Expected at least one title"):
        build_schema_signature(
            endpoint="title_index",
            metadata={"params": {}, "url": "https://example.invalid/api/title_list/allV2"},
            parsed=Response(),
        )


def test_build_schema_signature_rejects_empty_title_detail_chapter_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects title_detail payloads with no chapters."""
    monkeypatch.setattr(
        "mloader.infrastructure.mangaplus.capture_signatures.MessageToDict",
        lambda *_args, **_kwargs: {
            "success": {"title_detail_view": {"title": {}, "chapter_list_group": []}}
        },
    )

    with pytest.raises(CaptureVerificationError, match="Expected at least one chapter group"):
        build_schema_signature(
            endpoint="title_detailV3",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=Response(),
        )


def test_build_schema_signature_rejects_empty_first_chapter_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature rejects title_detail payloads with empty first_chapter_list."""
    monkeypatch.setattr(
        "mloader.infrastructure.mangaplus.capture_signatures.MessageToDict",
        lambda *_args, **_kwargs: {
            "success": {
                "title_detail_view": {
                    "title": {},
                    "chapter_list_group": [{"first_chapter_list": []}],
                }
            }
        },
    )

    with pytest.raises(
        CaptureVerificationError, match="Expected at least one chapter in first_chapter_list"
    ):
        build_schema_signature(
            endpoint="title_detailV3",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=Response(),
        )


def test_build_schema_signature_accepts_flat_title_detail_chapter_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema signature accepts mobile title_detail flat chapter lists."""
    monkeypatch.setattr(
        "mloader.infrastructure.mangaplus.capture_signatures.MessageToDict",
        lambda *_args, **_kwargs: {
            "success": {
                "title_detail_view": {
                    "title": {},
                    "chapter_list": [{"chapter_id": 1024959, "name": "#001"}],
                }
            }
        },
    )

    signature = json.loads(
        build_schema_signature(
            endpoint="title_detailV3",
            metadata={"params": {}, "url": "https://example.invalid"},
            parsed=Response(),
        )
    )

    assert signature["chapter_source"] == "chapter_list"
    assert signature["chapter_keys"] == ["chapter_id", "name"]
