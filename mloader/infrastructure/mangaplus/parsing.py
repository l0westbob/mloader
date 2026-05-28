"""Parse MangaPlus protobuf response bytes into stable domain DTOs."""

from __future__ import annotations

from typing import Any, Protocol

from mloader.domain.manga import MangaViewer, TitleDetail
from mloader.errors import APIResponseError
from mloader.infrastructure.mangaplus import mappers
from mloader.infrastructure.mangaplus.api_response import (
    classify_api_response_payload,
    format_api_payload_problem,
)
from mloader.response_pb2 import Response


class ParsedResponse(Protocol):
    """Minimal parsed response object produced by protobuf response types."""

    success: Any


class ResponseType(Protocol):
    """Factory protocol for protobuf response classes used by parsers."""

    @staticmethod
    def FromString(content: bytes) -> ParsedResponse:
        """Parse raw protobuf bytes into a response message."""


def has_message_field(message: object, field_name: str) -> bool:
    """Return whether protobuf ``message`` has explicit ``field_name`` set."""
    has_field = getattr(message, "HasField", None)
    if not callable(has_field):
        return True
    try:
        return bool(has_field(field_name))
    except ValueError:
        return False


def raise_payload_error(content: bytes, *, context: str, payload_name: str) -> None:
    """Raise a typed response error for a missing payload branch."""
    classification = classify_api_response_payload(content)
    if classification.kind in {"api_error", "empty"}:
        kind = "api_error" if classification.kind == "api_error" else "empty"
        raise APIResponseError(
            format_api_payload_problem(classification, context=context),
            kind=kind,
            code=classification.error.code if classification.error else None,
        )

    raise APIResponseError(
        f"MangaPlus API returned no {payload_name} payload; possible API schema drift.",
        kind="unknown",
    )


def parse_manga_viewer_response(
    content: bytes,
    *,
    response_type: ResponseType = Response,
) -> MangaViewer:
    """Parse and validate a MangaPlus viewer response into a domain DTO."""
    parsed = response_type.FromString(content)
    success = parsed.success
    if not has_message_field(success, "manga_viewer"):
        raise_payload_error(
            content,
            context="manga_viewer",
            payload_name="manga_viewer",
        )

    viewer = success.manga_viewer
    if viewer.title_id == 0 or viewer.chapter_id == 0:
        raise APIResponseError(
            "MangaPlus API returned manga_viewer payload without title/chapter IDs.",
            kind="unknown",
        )
    return mappers.manga_viewer_from_proto(viewer)


def parse_title_detail_response(
    content: bytes,
    *,
    response_type: ResponseType = Response,
) -> TitleDetail:
    """Parse and validate a MangaPlus title-detail response into a domain DTO."""
    parsed = response_type.FromString(content)
    success = parsed.success
    if not has_message_field(success, "title_detail_view"):
        raise_payload_error(
            content,
            context="title_detailV3",
            payload_name="title_detail_view",
        )

    title_detail = success.title_detail_view
    title = title_detail.title
    if title.title_id == 0 or not title.name:
        raise APIResponseError(
            "MangaPlus API returned title_detail_view without title identity.",
            kind="unknown",
        )

    mapped = mappers.title_detail_from_proto(title_detail)
    if not mapped.chapter_groups:
        raise APIResponseError(
            "MangaPlus API returned title_detail_view without chapter groups or flat chapter list.",
            kind="unknown",
        )
    if not mapped.chapters:
        raise APIResponseError(
            "MangaPlus API returned title_detail_view without chapter entries.",
            kind="unknown",
        )
    return mapped
