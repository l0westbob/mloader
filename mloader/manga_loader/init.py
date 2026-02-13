"""Compose loader mixins into the concrete ``MangaLoader`` class."""

from __future__ import annotations

from typing import Literal

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mloader.types import ExporterFactoryLike

from .api import APILoaderMixin
from .capture import APIPayloadCapture
from .decryption import DecryptionMixin
from .downloader import DownloadMixin
from .normalization import NormalizationMixin


class MangaLoader(APILoaderMixin, NormalizationMixin, DownloadMixin, DecryptionMixin):
    """Main orchestrator class for manga download operations."""

    def __init__(
        self,
        exporter: ExporterFactoryLike,
        quality: str,
        split: bool,
        meta: bool,
        destination: str = "mloader_downloads",
        output_format: Literal["raw", "cbz", "pdf"] = "cbz",
        session: Session | None = None,
        api_url: str = "https://jumpg-api.tokyo-cdn.com",
        request_timeout: tuple[float, float] = (5.0, 30.0),
        retries: int = 3,
        capture_api_dir: str | None = None,
    ) -> None:
        """Initialize loader configuration, transport defaults, and headers."""
        self.meta = meta
        self.exporter = exporter
        self.destination = destination
        self.output_format = output_format
        self.quality = quality
        self.split = split
        self.request_timeout = request_timeout
        self.payload_capture = APIPayloadCapture(capture_api_dir) if capture_api_dir else None
        self.session = session or Session()
        self._configure_transport(self.session, retries)
        self.session.headers.update(
            {
                "User-Agent": "JumpPlus/1 CFNetwork/1333.0.4 Darwin/21.5.0",
            }
        )
        self._api_url = api_url

    @staticmethod
    def _configure_transport(session: Session, retries: int) -> None:
        """Configure HTTP retry policy for transient API failures."""
        retry_policy = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_policy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
