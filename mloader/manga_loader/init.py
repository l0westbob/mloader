from .api import APILoaderMixin
from .normalization import NormalizationMixin
from .downloader import DownloadMixin
from .decryption import DecryptionMixin
from requests import Session

class MangaLoader(APILoaderMixin, NormalizationMixin, DownloadMixin, DecryptionMixin):
    """
    Main class for downloading manga. Composes functionality from API calls,
    normalization, downloading, and decryption via mixins.
    """
    def __init__(self, exporter, quality, split, meta, session=Session(), api_url="https://jumpg-api.tokyo-cdn.com"):
        self.meta = meta
        self.exporter = exporter
        self.quality = quality
        self.split = split
        self.session = session
        self.session.headers.update(
            {
                "User-Agent": "JumpPlus/1 CFNetwork/1333.0.4 Darwin/21.5.0",
            }
        )
        self._api_url = api_url