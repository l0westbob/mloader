"""Schema-signature builders for MangaPlus capture verification."""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.parse import urlparse

from google.protobuf.json_format import MessageToDict
from mloader.infrastructure.mangaplus.api_response import ApiPayloadClassification
from mloader.infrastructure.mangaplus.capture_metadata import CaptureVerificationError
from mloader.response_pb2 import Response


def as_dict(value: object, context: str) -> dict[str, Any]:
    """Return ``value`` as dictionary or raise descriptive verification error."""
    if not isinstance(value, dict):
        raise CaptureVerificationError(f"Expected object at {context}")
    return cast(dict[str, Any], value)


def as_list(value: object, context: str) -> list[Any]:
    """Return ``value`` as list or raise descriptive verification error."""
    if not isinstance(value, list):
        raise CaptureVerificationError(f"Expected list at {context}")
    return cast(list[Any], value)


def build_schema_signature(
    *,
    endpoint: str,
    metadata: dict[str, Any],
    parsed: Response,
) -> str:
    """Build normalized schema signature JSON for baseline drift checks."""
    response_data = MessageToDict(
        parsed,
        preserving_proto_field_name=True,
        use_integers_for_enums=True,
    )
    success = as_dict(response_data.get("success"), "response.success")
    params = as_dict(metadata.get("params"), "metadata.params")

    signature: dict[str, object] = {
        "endpoint": endpoint,
        "url_path": urlparse(str(metadata.get("url", ""))).path,
        "meta_keys": sorted(metadata.keys()),
        "param_keys": sorted(params.keys()),
        "success_keys": sorted(success.keys()),
    }

    if endpoint == "manga_viewer":
        viewer = as_dict(success.get("manga_viewer"), "response.success.manga_viewer")
        signature["payload_keys"] = sorted(viewer.keys())

        pages = as_list(viewer.get("pages", []), "response.success.manga_viewer.pages")
        if metadata.get("expected_runtime_error") == "subscription_required":
            signature["payload_state"] = "subscription_required"
            return json.dumps(signature, sort_keys=True)

        if not pages:
            raise CaptureVerificationError(
                "Expected at least one page in response.success.manga_viewer.pages"
            )
        signature["payload_state"] = "pages"
        first_page = as_dict(pages[0], "response.success.manga_viewer.pages[0]")
        last_page = as_dict(pages[-1], "response.success.manga_viewer.pages[-1]")
        signature["first_page_keys"] = sorted(first_page.keys())
        signature["last_page_keys"] = sorted(last_page.keys())
        signature["manga_page_keys"] = sorted(
            as_dict(
                first_page.get("manga_page"), "response.success.manga_viewer.pages[0].manga_page"
            ).keys()
        )
        signature["last_page_payload_keys"] = sorted(
            as_dict(
                last_page.get("last_page"), "response.success.manga_viewer.pages[-1].last_page"
            ).keys()
        )
        return json.dumps(signature, sort_keys=True)

    if endpoint == "title_detailV3":
        title_detail = as_dict(
            success.get("title_detail_view"), "response.success.title_detail_view"
        )
        signature["payload_keys"] = sorted(title_detail.keys())
        signature["title_keys"] = sorted(
            as_dict(title_detail.get("title"), "response.success.title_detail_view.title").keys()
        )

        chapter_groups = title_detail.get("chapter_list_group")
        if chapter_groups:
            grouped_chapters = as_list(
                chapter_groups,
                "response.success.title_detail_view.chapter_list_group",
            )
            first_group = as_dict(
                grouped_chapters[0],
                "response.success.title_detail_view.chapter_list_group[0]",
            )
            signature["chapter_source"] = "chapter_list_group"
            signature["chapter_group_keys"] = sorted(first_group.keys())

            first_chapter_list = as_list(
                first_group.get("first_chapter_list"),
                "response.success.title_detail_view.chapter_list_group[0].first_chapter_list",
            )
            if not first_chapter_list:
                raise CaptureVerificationError(
                    "Expected at least one chapter in first_chapter_list for "
                    "response.success.title_detail_view"
                )
            first_chapter = as_dict(
                first_chapter_list[0],
                "response.success.title_detail_view.chapter_list_group[0].first_chapter_list[0]",
            )
            signature["chapter_keys"] = sorted(first_chapter.keys())
            return json.dumps(signature, sort_keys=True)

        flat_chapters = as_list(
            title_detail.get("chapter_list", []),
            "response.success.title_detail_view.chapter_list",
        )
        if not flat_chapters:
            raise CaptureVerificationError(
                "Expected at least one chapter group or flat chapter list in "
                "response.success.title_detail_view"
            )
        first_chapter = as_dict(
            flat_chapters[0],
            "response.success.title_detail_view.chapter_list[0]",
        )
        signature["chapter_source"] = "chapter_list"
        signature["chapter_keys"] = sorted(first_chapter.keys())
        return json.dumps(signature, sort_keys=True)

    if endpoint == "title_index":
        all_titles = as_dict(success.get("all_titles_view"), "response.success.all_titles_view")
        signature["payload_keys"] = sorted(all_titles.keys())
        title_groups = as_list(
            all_titles.get("title_groups"),
            "response.success.all_titles_view.title_groups",
        )
        if not title_groups:
            raise CaptureVerificationError(
                "Expected at least one group in response.success.all_titles_view.title_groups"
            )
        first_group = as_dict(title_groups[0], "response.success.all_titles_view.title_groups[0]")
        signature["title_group_keys"] = sorted(first_group.keys())
        titles = as_list(
            first_group.get("titles"),
            "response.success.all_titles_view.title_groups[0].titles",
        )
        if not titles:
            raise CaptureVerificationError(
                "Expected at least one title in response.success.all_titles_view.title_groups[0].titles"
            )
        first_title = as_dict(
            titles[0],
            "response.success.all_titles_view.title_groups[0].titles[0]",
        )
        signature["title_keys"] = sorted(first_title.keys())
        return json.dumps(signature, sort_keys=True)

    raise CaptureVerificationError(f"Unsupported endpoint '{endpoint}'")


def build_api_error_signature(
    *,
    endpoint: str,
    metadata: dict[str, Any],
    classification: ApiPayloadClassification,
) -> str:
    """Build normalized signature JSON for captured API error envelopes."""
    if classification.error is None:
        raise CaptureVerificationError("Expected API error details in payload classification")

    params = as_dict(metadata.get("params", {}), "metadata.params")
    signature: dict[str, object] = {
        "endpoint": endpoint,
        "url_path": urlparse(str(metadata.get("url", ""))).path,
        "meta_keys": sorted(metadata.keys()),
        "param_keys": sorted(params.keys()),
        "payload_classification": classification.kind,
        "api_error_code": classification.error.code,
        "api_error_language": classification.error.language,
        "api_error_title": classification.error.title,
    }
    return json.dumps(signature, sort_keys=True)
