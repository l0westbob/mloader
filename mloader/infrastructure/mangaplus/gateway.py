"""MangaPlus HTTP gateway and protobuf-to-domain parsing adapter."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Collection, Mapping
from typing import TypeVar, cast

from requests import Session

from mloader.domain.manga import MangaViewer, TitleDetail
from mloader.infrastructure.mangaplus import auth
from mloader.infrastructure.mangaplus import parsing as response_parsing
from mloader.infrastructure.mangaplus.settings import (
    DEFAULT_API_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRIES,
    MANGA_VIEWER_PATH,
    TITLE_DETAIL_PATH,
    api_url,
)
from mloader.infrastructure.mangaplus.transport import (
    apply_mobile_api_headers,
    capture_response_payload,
    configure_transport,
)
from mloader.types import PayloadCaptureLike, SessionLike

AuthParamsProvider = Callable[[], Mapping[str, str]]
CacheValue = TypeVar("CacheValue")


class MangaPlusGateway:
    """HTTP gateway for MangaPlus title-detail and manga-viewer endpoints."""

    def __init__(
        self,
        *,
        session: SessionLike | None = None,
        api_base_url: str = DEFAULT_API_BASE_URL,
        quality: str,
        split: bool,
        request_timeout: tuple[float, float] = DEFAULT_REQUEST_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        payload_capture: PayloadCaptureLike | None = None,
        auth_params_provider: AuthParamsProvider = auth.auth_params,
        viewer_cache_max_size: int = 512,
        title_cache_max_size: int = 256,
    ) -> None:
        """Initialize transport, auth, payload capture, and response caches."""
        self.session: SessionLike = session if session is not None else cast(SessionLike, Session())
        configure_transport(self.session, retries)
        apply_mobile_api_headers(self.session)
        self.api_base_url = api_base_url
        self.quality = quality
        self.split = split
        self.request_timeout = request_timeout
        self.payload_capture = payload_capture
        self.auth_params_provider = auth_params_provider
        self.viewer_cache_max_size = viewer_cache_max_size
        self.title_cache_max_size = title_cache_max_size
        self._viewer_cache: OrderedDict[str, MangaViewer] = OrderedDict()
        self._title_cache: OrderedDict[str, TitleDetail] = OrderedDict()

    def load_pages(self, chapter_id: str | int) -> MangaViewer:
        """Load and cache manga viewer data for a chapter."""
        cache_key = self._cache_key(chapter_id)
        cached_viewer = self._cache_get(self._viewer_cache, cache_key)
        if cached_viewer is not None:
            return cached_viewer

        url = self.build_manga_viewer_url()
        params = self.build_manga_viewer_params(chapter_id)
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        self.capture_payload(
            endpoint="manga_viewer",
            identifier=chapter_id,
            url=url,
            params=params,
            response_content=response.content,
        )
        viewer = response_parsing.parse_manga_viewer_response(response.content)
        self._cache_set(
            self._viewer_cache,
            cache_key,
            viewer,
            max_size=self.viewer_cache_max_size,
        )
        return viewer

    def get_title_details(self, title_id: str | int) -> TitleDetail:
        """Load and cache title-detail data for a title."""
        cache_key = self._cache_key(title_id)
        cached_title = self._cache_get(self._title_cache, cache_key)
        if cached_title is not None:
            return cached_title

        url = self.build_title_detail_url()
        params = self.build_title_detail_params(title_id)
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        self.capture_payload(
            endpoint="title_detailV3",
            identifier=title_id,
            url=url,
            params=params,
            response_content=response.content,
        )
        title_detail = response_parsing.parse_title_detail_response(response.content)
        self._cache_set(
            self._title_cache,
            cache_key,
            title_detail,
            max_size=self.title_cache_max_size,
        )
        return title_detail

    def build_manga_viewer_url(self) -> str:
        """Construct the full URL for the manga-viewer API endpoint."""
        return api_url(self.api_base_url, MANGA_VIEWER_PATH)

    def build_manga_viewer_params(self, chapter_id: str | int) -> dict[str, str | int]:
        """Assemble manga-viewer API query parameters."""
        split_value = "yes" if self.split else "no"
        return {
            **self.auth_params_provider(),
            "chapter_id": chapter_id,
            "split": split_value,
            "img_quality": self.quality,
        }

    def build_title_detail_url(self) -> str:
        """Construct the full URL for the title-detail API endpoint."""
        return api_url(self.api_base_url, TITLE_DETAIL_PATH)

    def build_title_detail_params(self, title_id: str | int) -> dict[str, str | int]:
        """Assemble title-detail API query parameters."""
        return {**self.auth_params_provider(), "title_id": title_id}

    def capture_payload(
        self,
        *,
        endpoint: str,
        identifier: str | int,
        url: str,
        params: Mapping[str, object],
        response_content: bytes,
    ) -> None:
        """Write API payload capture data when capture mode is enabled."""
        capture_response_payload(
            self.payload_capture,
            endpoint=endpoint,
            identifier=identifier,
            url=url,
            params=params,
            response_content=response_content,
        )

    def clear_run_caches(self) -> None:
        """Clear all cached API response DTOs."""
        self._viewer_cache.clear()
        self._title_cache.clear()

    def clear_title_caches(
        self,
        title_id: str | int,
        chapter_ids: Collection[int] | None = None,
    ) -> None:
        """Clear title-scoped API cache entries."""
        self._title_cache.pop(self._cache_key(title_id), None)
        if not chapter_ids:
            return
        for chapter_id in chapter_ids:
            self._viewer_cache.pop(self._cache_key(chapter_id), None)

    @staticmethod
    def _cache_key(identifier: str | int) -> str:
        """Return a normalized cache key for API identifiers."""
        return str(identifier)

    @staticmethod
    def _cache_get(cache: OrderedDict[str, CacheValue], key: str) -> CacheValue | None:
        """Return cached value by key and refresh LRU order."""
        if key not in cache:
            return None
        cache.move_to_end(key)
        return cache[key]

    @staticmethod
    def _cache_set(
        cache: OrderedDict[str, CacheValue],
        key: str,
        value: CacheValue,
        *,
        max_size: int,
    ) -> None:
        """Store cached value and evict oldest entries beyond ``max_size``."""
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > max_size:
            cache.popitem(last=False)
