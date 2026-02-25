"""Compose loader runtime services into the concrete ``MangaLoader`` facade."""

from __future__ import annotations

from typing import Literal

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mloader.domain.requests import DownloadSummary
from mloader.types import ExporterFactoryLike, PayloadCaptureLike

from .api import APILoaderMixin
from .capture import APIPayloadCapture
from .decryption import DecryptionMixin
from .download_services import DownloadServices
from .downloader import DownloadMixin
from .normalization import NormalizationMixin


class _LoaderRuntime(APILoaderMixin, NormalizationMixin, DownloadMixin, DecryptionMixin):
    """Internal runtime implementation composed from existing focused mixins."""

    def __init__(
        self,
        exporter: ExporterFactoryLike,
        quality: str,
        split: bool,
        meta: bool,
        destination: str,
        output_format: Literal["raw", "cbz", "pdf"],
        session: Session | None,
        api_url: str,
        request_timeout: tuple[float, float],
        retries: int,
        capture_api_dir: str | None,
        resume: bool,
        manifest_reset: bool,
        services: DownloadServices,
    ) -> None:
        """Initialize runtime dependencies and transport settings."""
        self.meta = meta
        self.exporter = exporter
        self.destination = destination
        self.output_format = output_format
        self.quality = quality
        self.split = split
        self.request_timeout = request_timeout
        self.resume = resume
        self.manifest_reset = manifest_reset
        self.services = services
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


class MangaLoader:
    """Facade object exposing the download API while composing internal runtime behavior."""

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
        resume: bool = True,
        manifest_reset: bool = False,
        services: DownloadServices | None = None,
    ) -> None:
        """Initialize the composed runtime and preserve public constructor contract."""
        self._runtime = _LoaderRuntime(
            exporter=exporter,
            quality=quality,
            split=split,
            meta=meta,
            destination=destination,
            output_format=output_format,
            session=session,
            api_url=api_url,
            request_timeout=request_timeout,
            retries=retries,
            capture_api_dir=capture_api_dir,
            resume=resume,
            manifest_reset=manifest_reset,
            services=services or DownloadServices.defaults(),
        )

    @property
    def session(self) -> Session:
        """Expose active HTTP session for tests and runtime introspection."""
        return self._runtime.session

    @property
    def destination(self) -> str:
        """Expose configured destination directory."""
        return self._runtime.destination

    @property
    def output_format(self) -> Literal["raw", "cbz", "pdf"]:
        """Expose configured chapter output format."""
        return self._runtime.output_format

    @property
    def request_timeout(self) -> tuple[float, float]:
        """Expose configured request timeout tuple."""
        return self._runtime.request_timeout

    @property
    def payload_capture(self) -> PayloadCaptureLike | None:
        """Expose payload capture backend when capture mode is enabled."""
        return self._runtime.payload_capture

    @staticmethod
    def _configure_transport(session: Session, retries: int) -> None:
        """Proxy transport configuration for compatibility with existing tests/usages."""
        _LoaderRuntime._configure_transport(session, retries)

    def download(
        self,
        *,
        title_ids: set[int] | frozenset[int] | None = None,
        chapter_ids: set[int] | frozenset[int] | None = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> DownloadSummary:
        """Delegate download orchestration to the composed runtime."""
        return self._runtime.download(
            title_ids=title_ids,
            chapter_ids=chapter_ids,
            min_chapter=min_chapter,
            max_chapter=max_chapter,
            last_chapter=last_chapter,
        )
