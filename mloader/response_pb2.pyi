"""Typing stub for generated MangaPlus protobuf classes."""

from __future__ import annotations

from typing import Any, Self

from google.protobuf.message import Message

class _DynamicMessage(Message):
    """Dynamic protobuf message surface generated at runtime."""

    def __getattr__(self, name: str) -> Any: ...
    def __setattr__(self, name: str, value: Any) -> None: ...
    def HasField(self, field_name: str) -> bool: ...
    def ListFields(self) -> list[tuple[Any, Any]]: ...
    def SerializeToString(self, **kwargs: Any) -> bytes: ...
    @classmethod
    def FromString(cls, s: Any) -> Self: ...

class Response(_DynamicMessage):
    """Top-level MangaPlus response message."""

    success: Any
