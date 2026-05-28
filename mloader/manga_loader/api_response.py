"""MangaPlus API response classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from google.protobuf.message import DecodeError

from mloader.response_pb2 import Response  # type: ignore

ApiPayloadKind = Literal["success", "api_error", "empty", "unknown"]

_ERROR_CODE_PATTERN = re.compile(r"\((?P<code>\d+)\)\s*$")
_MAX_PARSE_DEPTH = 8


@dataclass(frozen=True, slots=True)
class MangaPlusApiError:
    """Application-level error message embedded in a MangaPlus protobuf payload."""

    title: str
    body: str
    code: str | None = None
    language: int | None = None


@dataclass(frozen=True, slots=True)
class ApiPayloadClassification:
    """Typed classification for raw MangaPlus response bytes."""

    kind: ApiPayloadKind
    error: MangaPlusApiError | None = None

    @property
    def description(self) -> str:
        """Return a concise human-readable classification summary."""
        if self.kind == "api_error" and self.error is not None:
            code = f" code={self.error.code}" if self.error.code else ""
            return f"api_error{code}: {self.error.title}: {self.error.body}"
        return self.kind


def classify_api_response_payload(payload: bytes) -> ApiPayloadClassification:
    """Classify raw MangaPlus payload bytes without assuming a success schema."""
    if not payload:
        return ApiPayloadClassification(kind="empty")

    api_error = extract_api_error(payload)
    if api_error is not None:
        return ApiPayloadClassification(kind="api_error", error=api_error)

    try:
        parsed = Response.FromString(payload)
    except DecodeError:
        return ApiPayloadClassification(kind="unknown")

    if _has_populated_success(parsed):
        return ApiPayloadClassification(kind="success")

    return ApiPayloadClassification(kind="unknown")


def format_api_payload_problem(
    classification: ApiPayloadClassification,
    *,
    context: str,
) -> str:
    """Format a stable diagnostic message for non-success API payloads."""
    if classification.kind == "api_error" and classification.error is not None:
        error = classification.error
        code = f" ({error.code})" if error.code else ""
        return (
            f"MangaPlus API returned an application error for {context}{code}: "
            f"{error.title}: {error.body}"
        )

    if classification.kind == "empty":
        return f"MangaPlus API returned an empty payload for {context}."

    return (
        f"MangaPlus API returned an undecodable or unknown payload for {context}; "
        "this may indicate API schema drift."
    )


def extract_api_error(payload: bytes) -> MangaPlusApiError | None:
    """Extract the first useful MangaPlus application error envelope, if present."""
    for field_number, wire_type, value in _iter_fields(payload):
        if field_number != 2 or wire_type != 2 or not isinstance(value, bytes):
            continue

        messages = [
            message for message in _extract_error_messages(value) if message.body or message.title
        ]
        if not messages:
            continue

        for message in messages:
            if message.language in (None, 0) and _looks_english(message.body):
                return message
        return messages[0]

    return None


def _has_populated_success(parsed: Response) -> bool:
    """Return whether ``parsed`` contains a non-empty success envelope."""
    try:
        if not parsed.HasField("success"):
            return False
    except ValueError:
        return False
    return bool(parsed.success.ListFields())


def _extract_error_messages(error_payload: bytes) -> list[MangaPlusApiError]:
    """Extract localized error messages from the raw top-level error branch."""
    messages: list[MangaPlusApiError] = []
    for _field_number, wire_type, value in _iter_fields(error_payload):
        if wire_type != 2 or not isinstance(value, bytes):
            continue
        message = _parse_error_message(value)
        if message is not None:
            messages.append(message)
    return messages


def _parse_error_message(payload: bytes) -> MangaPlusApiError | None:
    """Parse one localized API error message from a raw protobuf submessage."""
    title = ""
    body = ""
    language: int | None = None

    for field_number, wire_type, value in _iter_fields(payload):
        if wire_type == 2 and isinstance(value, bytes):
            if field_number == 1:
                title = _decode_text(value)
            elif field_number == 2:
                body = _decode_text(value)
        elif wire_type == 0 and isinstance(value, int) and field_number == 6:
            language = value

    if not title and not body:
        return None

    return MangaPlusApiError(
        title=title,
        body=body,
        code=_extract_error_code(body),
        language=language,
    )


def _extract_error_code(message: str) -> str | None:
    """Return a trailing MangaPlus numeric error code from ``message``."""
    match = _ERROR_CODE_PATTERN.search(message)
    if match is None:
        return None
    return match.group("code")


def _looks_english(text: str) -> bool:
    """Return a lightweight signal for the English localized error branch."""
    if not text:
        return False
    return text.isascii() and "Manga" in text


def _decode_text(value: bytes) -> str:
    """Decode protobuf string bytes defensively."""
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _iter_fields(
    payload: bytes,
    *,
    depth: int = 0,
) -> list[tuple[int, int, int | bytes]]:
    """Return raw protobuf fields for the wire types used by MangaPlus envelopes."""
    if depth > _MAX_PARSE_DEPTH:
        return []

    fields: list[tuple[int, int, int | bytes]] = []
    index = 0
    length = len(payload)
    while index < length:
        try:
            key, index = _read_varint(payload, index)
        except ValueError:
            return fields

        field_number = key >> 3
        wire_type = key & 0x07
        if field_number <= 0:
            return fields

        if wire_type == 0:
            try:
                value, index = _read_varint(payload, index)
            except ValueError:
                return fields
            fields.append((field_number, wire_type, value))
            continue

        if wire_type == 1:
            if index + 8 > length:
                return fields
            index += 8
            fields.append((field_number, wire_type, b""))
            continue

        if wire_type == 2:
            try:
                size, index = _read_varint(payload, index)
            except ValueError:
                return fields
            end = index + size
            if end > length:
                return fields
            fields.append((field_number, wire_type, payload[index:end]))
            index = end
            continue

        if wire_type == 5:
            if index + 4 > length:
                return fields
            index += 4
            fields.append((field_number, wire_type, b""))
            continue

        return fields

    return fields


def _read_varint(payload: bytes, index: int) -> tuple[int, int]:
    """Read a protobuf varint from ``payload`` starting at ``index``."""
    shift = 0
    value = 0
    while index < len(payload):
        byte = payload[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, index
        shift += 7
        if shift >= 64:
            raise ValueError("varint too long")
    raise ValueError("truncated varint")
