"""Compose loader mixins into the concrete ``MangaLoader`` class."""

from __future__ import annotations

from typing import Any, Callable

from requests import Session

from .api import APILoaderMixin
from .decryption import DecryptionMixin
from .downloader import DownloadMixin
from .normalization import NormalizationMixin


class MangaLoader(APILoaderMixin, NormalizationMixin, DownloadMixin, DecryptionMixin):
    """Main orchestrator class for manga download operations."""

    def __init__(
        self,
        exporter: Callable[..., Any],
        quality: str,
        split: bool,
        meta: bool,
        session: Session | None = None,
        api_url: str = "https://jumpg-api.tokyo-cdn.com",
    ) -> None:
        """Initialize loader configuration and HTTP session headers."""
        self.meta = meta
        self.exporter = exporter
        self.quality = quality
        self.split = split
        self.session = session or Session()
        self.session.headers.update(
            {
                "User-Agent": "JumpPlus/1 CFNetwork/1333.0.4 Darwin/21.5.0",
            }
        )
        self._api_url = api_url
