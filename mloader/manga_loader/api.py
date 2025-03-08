from functools import lru_cache
from typing import Union
from mloader.config import AUTH_PARAMS
from mloader.response_pb2 import Response # type: ignore


def _parse_manga_viewer_response(content: bytes) -> 'MangaViewer':
    """Parse the API response to extract the MangaViewer object."""
    parsed = Response.FromString(content)
    return parsed.success.manga_viewer


def _build_title_detail_params(title_id: Union[str, int]) -> dict:
    """Assemble the query parameters for the title details API request."""
    return {**AUTH_PARAMS, "title_id": title_id}


def _parse_title_detail_response(content: bytes) -> 'TitleDetailView':
    """Parse the API response to extract the TitleDetailView object."""
    parsed = Response.FromString(content)
    return parsed.success.title_detail_view


class APILoaderMixin:
    @lru_cache(None)
    def _load_pages(self, chapter_id: Union[str, int]) -> 'MangaViewer':
        """
        Retrieve and cache manga viewer data for a given chapter.
        """
        url = self._build_manga_viewer_url()
        params = self._build_manga_viewer_params(chapter_id)
        response = self.session.get(url, params=params)
        return _parse_manga_viewer_response(response.content)

    def _build_manga_viewer_url(self) -> str:
        """Construct the full URL for the manga viewer API endpoint."""
        return f"{self._api_url}/api/manga_viewer"

    def _build_manga_viewer_params(self, chapter_id: Union[str, int]) -> dict:
        """Assemble the query parameters for the manga viewer API request."""
        split_value = "yes" if self.split else "no"
        return {**AUTH_PARAMS, "chapter_id": chapter_id, "split": split_value, "img_quality": self.quality}

    @lru_cache(None)
    def _get_title_details(self, title_id: Union[str, int]) -> 'TitleDetailView':
        """
        Retrieve and cache detailed information for a given manga title.
        """
        url = self._build_title_detail_url()
        params = _build_title_detail_params(title_id)
        response = self.session.get(url, params=params)
        return _parse_title_detail_response(response.content)

    def _build_title_detail_url(self) -> str:
        """Construct the full URL for the title details API endpoint."""
        return f"{self._api_url}/api/title_detailV3"

