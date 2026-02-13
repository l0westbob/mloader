"""API helpers and cached fetch methods for MangaPlus endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import Union, cast

from mloader.config import AUTH_PARAMS
from mloader.response_pb2 import Response  # type: ignore
from mloader.types import MangaViewerLike, SessionLike, TitleDumpLike


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

    @lru_cache(None)
    def _load_pages(self, chapter_id: Union[str, int]) -> MangaViewerLike:
        """
        Retrieve and cache manga viewer data for a given chapter.
        """
        url = self._build_manga_viewer_url()
        params = self._build_manga_viewer_params(chapter_id)
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        return _parse_manga_viewer_response(response.content)

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

    @lru_cache(None)
    def _get_title_details(self, title_id: Union[str, int]) -> TitleDumpLike:
        """
        Retrieve and cache detailed information for a given manga title.
        """
        url = self._build_title_detail_url()
        params = _build_title_detail_params(title_id)
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        return _parse_title_detail_response(response.content)

    def _build_title_detail_url(self) -> str:
        """Construct the full URL for the title details API endpoint."""
        return f"{self._api_url}/api/title_detailV3"
