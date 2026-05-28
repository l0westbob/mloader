"""Page image fetching and export services."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterator
from itertools import count

import click

from mloader.constants import PageType
from mloader.domain.manga import MangaPage
from mloader.manga_loader.decryption import _convert_hex_to_bytes, _xor_decrypt
from mloader.types import ExporterLike, SessionLike


class PageImageService:
    """Download and decrypt chapter image payloads."""

    @staticmethod
    def download_image(
        session: SessionLike,
        request_timeout: tuple[float, float],
        url: str,
    ) -> bytes:
        """Download one image blob from ``url`` using configured session settings."""
        response = session.get(url, timeout=request_timeout)
        response.raise_for_status()
        return response.content

    @staticmethod
    def fetch_encrypted_data(
        session: SessionLike,
        request_timeout: tuple[float, float],
        url: str,
    ) -> bytearray:
        """Download encrypted image bytes from the source URL."""
        response = session.get(url, timeout=request_timeout)
        response.raise_for_status()
        return bytearray(response.content)

    @staticmethod
    def decrypt_image(
        session: SessionLike,
        request_timeout: tuple[float, float],
        url: str,
        encryption_hex: str,
    ) -> bytearray:
        """Download and decrypt one encrypted image payload."""
        encrypted_data = PageImageService.fetch_encrypted_data(session, request_timeout, url)
        encryption_key = _convert_hex_to_bytes(encryption_hex)
        return _xor_decrypt(encrypted_data, encryption_key)

    @staticmethod
    def fetch_page_image(
        page: MangaPage,
        *,
        download_image: Callable[[str], bytes],
        decrypt_image: Callable[[str, str], bytearray],
    ) -> bytes:
        """Return raw or decrypted page bytes depending on encryption key presence."""
        encryption_key = str(getattr(page, "encryption_key", ""))
        if encryption_key:
            return bytes(decrypt_image(page.image_url, encryption_key))
        return download_image(page.image_url)


class PageExportService:
    """Export chapter pages with stable page-index handling."""

    @staticmethod
    def _double_page_index(page_index: int, page_counter: Iterator[int]) -> range:
        """Build DOUBLE-page index marker with inclusive ``stop`` naming semantics."""
        paired_page_index = next(page_counter)
        return range(page_index, paired_page_index)

    @staticmethod
    def export_pages(
        pages: Collection[MangaPage],
        chapter_name: str,
        exporter: ExporterLike,
        *,
        fetch_page_image: Callable[[MangaPage], bytes],
    ) -> None:
        """Stream chapter pages through exporter with DOUBLE-page index mapping."""
        with click.progressbar(pages, label=chapter_name, show_pos=True) as progress_bar:
            page_counter = count()
            for page_index, page in zip(page_counter, progress_bar):
                output_index: int | range = page_index
                if PageType(page.page_type) == PageType.DOUBLE:
                    output_index = PageExportService._double_page_index(
                        page_index,
                        page_counter,
                    )

                if exporter.skip_image(output_index):
                    continue

                image_blob = fetch_page_image(page)
                exporter.add_image(image_blob, output_index)
