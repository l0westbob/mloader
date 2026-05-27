"""Shared typed HTTP fakes for infrastructure tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Self

import requests


class BytesResponse:
    """Minimal bytes response double with requests-like status handling."""

    def __init__(self, content: bytes | None = None, *, status_code: int = 200) -> None:
        """Store binary response content and status code."""
        self.content = content if content is not None else b""
        self.status_code = status_code
        self.status_checked = False

    def raise_for_status(self) -> None:
        """Raise HTTPError for failed status codes."""
        self.status_checked = True
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(f"{self.status_code} error", response=response)


class TextResponse:
    """Minimal text response double with requests-like status handling."""

    def __init__(self, text: str = "", *, status_code: int = 200) -> None:
        """Store text response content and status code."""
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Raise HTTPError for failed status codes."""
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(f"{self.status_code} error", response=response)


class BytesMappingSession:
    """Context-manager session serving binary payloads by URL."""

    def __init__(self, payloads: Mapping[str, bytes | BytesResponse]) -> None:
        """Store URL-to-response mapping and initialize call tracking."""
        self.payloads = payloads
        self.calls: list[tuple[str, Mapping[str, object] | None, tuple[float, float]]] = []
        self.headers: dict[str, str] = {}

    def __enter__(self) -> Self:
        """Support requests.Session context manager usage."""
        return self

    def __exit__(self, *args: object) -> None:
        """Support requests.Session context manager usage."""
        _ = args

    def get(
        self,
        url: str,
        params: Mapping[str, object] | None = None,
        timeout: tuple[float, float] = (5.0, 30.0),
    ) -> BytesResponse:
        """Record request details and return the mapped response."""
        self.calls.append((url, params, timeout))
        payload = self.payloads[url]
        if isinstance(payload, BytesResponse):
            return payload
        return BytesResponse(content=payload)


class TextMappingSession:
    """Context-manager session serving text payloads by URL."""

    def __init__(self, payloads: Mapping[str, str | TextResponse]) -> None:
        """Store URL-to-response mapping and initialize call tracking."""
        self.payloads = payloads
        self.calls: list[tuple[str, tuple[float, float]]] = []

    def __enter__(self) -> Self:
        """Support requests.Session context manager usage."""
        return self

    def __exit__(self, *args: object) -> None:
        """Support requests.Session context manager usage."""
        _ = args

    def get(self, url: str, timeout: tuple[float, float] = (5.0, 30.0)) -> TextResponse:
        """Record request details and return the mapped response."""
        self.calls.append((url, timeout))
        payload = self.payloads[url]
        if isinstance(payload, TextResponse):
            return payload
        return TextResponse(text=payload)
