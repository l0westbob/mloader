"""API helpers and cached fetch methods for MangaPlus endpoints."""

from __future__ import annotations

from collections import OrderedDict
from typing import Collection, Mapping, Union, cast

from mloader.config import AUTH_PARAMS
from mloader.response_pb2 import Response  # type: ignore
from mloader.types import MangaViewerLike, PayloadCaptureLike, SessionLike, TitleDumpLike


def _parse_manga_viewer_response(content: bytes) -> MangaViewerLike:
    """Parse the API response to extract the MangaViewer object."""
    parsed = Response.FromString(content)
    return cast(MangaViewerLike, parsed.success.manga_viewer)


def _build_title_detail_params(title_id: Union[str, int]) -> dict[str, str | int]:
    """Assemble the query parameters for the title details API request."""
    return {**AUTH_PARAMS, "title_id": title_id}


def _parse_title_detail_response(content: bytes) -> TitleDumpLike:
    """Parse the API response to extract the TitleDetailView object."""
    parsed = Response.FromString(content)
    return cast(TitleDumpLike, parsed.success.title_detail_view)


class APILoaderMixin:
    """Provide cached API calls for chapter viewer and title details."""

    session: SessionLike
    _api_url: str
    quality: str
    split: bool
    request_timeout: tuple[float, float]
    payload_capture: PayloadCaptureLike | None
    _viewer_cache_max_size: int = 512
    _title_cache_max_size: int = 256

    def _load_pages(self, chapter_id: Union[str, int]) -> MangaViewerLike:
        """
        Retrieve and cache manga viewer data for a given chapter.
        """
        chapter_cache_key = self._cache_key(chapter_id)
        cached_viewer = self._viewer_cache_get(chapter_cache_key)
        if cached_viewer is not None:
            return cached_viewer

        url = self._build_manga_viewer_url()
        params = self._build_manga_viewer_params(chapter_id)
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        self._capture_payload(
            endpoint="manga_viewer",
            identifier=chapter_id,
            url=url,
            params=params,
            response_content=response.content,
        )
        parsed_viewer = _parse_manga_viewer_response(response.content)
        self._viewer_cache_set(chapter_cache_key, parsed_viewer)
        return parsed_viewer

    def _build_manga_viewer_url(self) -> str:
        """Construct the full URL for the manga viewer API endpoint."""
        return f"{self._api_url}/api/manga_viewer"

    def _build_manga_viewer_params(self, chapter_id: Union[str, int]) -> dict[str, str | int]:
        """Assemble the query parameters for the manga viewer API request."""
        split_value = "yes" if self.split else "no"
        return {
            **AUTH_PARAMS,
            "chapter_id": chapter_id,
            "split": split_value,
            "img_quality": self.quality,
        }

    def _capture_payload(
        self,
        *,
        endpoint: str,
        identifier: str | int,
        url: str,
        params: Mapping[str, object],
        response_content: bytes,
    ) -> None:
        """Write API payload capture data when capture mode is enabled."""
        if self.payload_capture is None:
            return

        self.payload_capture.capture(
            endpoint=endpoint,
            identifier=identifier,
            url=url,
            params=params,
            response_content=response_content,
        )

    def _get_title_details(self, title_id: Union[str, int]) -> TitleDumpLike:
        """
        Retrieve and cache detailed information for a given manga title.
        """
        title_cache_key = self._cache_key(title_id)
        cached_title = self._title_cache_get(title_cache_key)
        if cached_title is not None:
            return cached_title

        url = self._build_title_detail_url()
        params = _build_title_detail_params(title_id)
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        self._capture_payload(
            endpoint="title_detailV3",
            identifier=title_id,
            url=url,
            params=params,
            response_content=response.content,
        )
        parsed_title = _parse_title_detail_response(response.content)
        self._title_cache_set(title_cache_key, parsed_title)
        return parsed_title

    def _build_title_detail_url(self) -> str:
        """Construct the full URL for the title details API endpoint."""
        return f"{self._api_url}/api/title_detailV3"

    def _clear_api_caches_for_run(self) -> None:
        """Clear all API response caches for the active loader instance."""
        self._get_viewer_cache().clear()
        self._get_title_cache().clear()

    def _clear_api_caches_for_title(
        self,
        title_id: int | str,
        chapter_ids: Collection[int] | None = None,
    ) -> None:
        """Clear title-scoped API cache entries after one title is processed."""
        self._get_title_cache().pop(self._cache_key(title_id), None)
        if not chapter_ids:
            return
        viewer_cache = self._get_viewer_cache()
        for chapter_id in chapter_ids:
            viewer_cache.pop(self._cache_key(chapter_id), None)

    def _cache_key(self, identifier: int | str) -> str:
        """Return a normalized cache key for API identifiers."""
        return str(identifier)

    def _get_viewer_cache(self) -> OrderedDict[str, MangaViewerLike]:
        """Return the per-instance chapter-viewer cache."""
        if not hasattr(self, "_viewer_cache"):
            self._viewer_cache: OrderedDict[str, MangaViewerLike] = OrderedDict()
        return self._viewer_cache

    def _get_title_cache(self) -> OrderedDict[str, TitleDumpLike]:
        """Return the per-instance title-detail cache."""
        if not hasattr(self, "_title_cache"):
            self._title_cache: OrderedDict[str, TitleDumpLike] = OrderedDict()
        return self._title_cache

    def _viewer_cache_get(self, key: str) -> MangaViewerLike | None:
        """Return cached viewer payload by key and refresh LRU order."""
        cache = self._get_viewer_cache()
        if key not in cache:
            return None
        cache.move_to_end(key)
        return cache[key]

    def _viewer_cache_set(self, key: str, value: MangaViewerLike) -> None:
        """Store viewer payload and evict oldest entries beyond max size."""
        cache = self._get_viewer_cache()
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > self._viewer_cache_max_size:
            cache.popitem(last=False)

    def _title_cache_get(self, key: str) -> TitleDumpLike | None:
        """Return cached title payload by key and refresh LRU order."""
        cache = self._get_title_cache()
        if key not in cache:
            return None
        cache.move_to_end(key)
        return cache[key]

    def _title_cache_set(self, key: str, value: TitleDumpLike) -> None:
        """Store title payload and evict oldest entries beyond max size."""
        cache = self._get_title_cache()
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > self._title_cache_max_size:
            cache.popitem(last=False)
