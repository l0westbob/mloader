from types import SimpleNamespace

from mloader.manga_loader import api


class DummySession:
    def __init__(self, content=b"payload"):
        self.content = content
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return SimpleNamespace(content=self.content)


class DummyLoader(api.APILoaderMixin):
    def __init__(self, split=True, quality="high"):
        self._api_url = "https://api.example"
        self.split = split
        self.quality = quality
        self.session = DummySession()


def test_parse_manga_viewer_response(monkeypatch):
    sentinel = object()

    class FakeResponse:
        @staticmethod
        def FromString(_content):
            return SimpleNamespace(success=SimpleNamespace(manga_viewer=sentinel))

    monkeypatch.setattr(api, "Response", FakeResponse)

    assert api._parse_manga_viewer_response(b"raw") is sentinel


def test_parse_title_detail_response(monkeypatch):
    sentinel = object()

    class FakeResponse:
        @staticmethod
        def FromString(_content):
            return SimpleNamespace(success=SimpleNamespace(title_detail_view=sentinel))

    monkeypatch.setattr(api, "Response", FakeResponse)

    assert api._parse_title_detail_response(b"raw") is sentinel


def test_build_title_detail_params_includes_auth_values():
    params = api._build_title_detail_params(123)

    assert params["title_id"] == 123
    assert "app_ver" in params
    assert "secret" in params


def test_manga_viewer_url_and_params():
    loader = DummyLoader(split=False, quality="low")

    assert loader._build_manga_viewer_url() == "https://api.example/api/manga_viewer"

    params = loader._build_manga_viewer_params(10)
    assert params["chapter_id"] == 10
    assert params["split"] == "no"
    assert params["img_quality"] == "low"


def test_load_pages_uses_cache(monkeypatch):
    api.APILoaderMixin._load_pages.cache_clear()
    loader = DummyLoader()

    monkeypatch.setattr(api, "_parse_manga_viewer_response", lambda content: {"parsed": content})

    first = loader._load_pages(5)
    second = loader._load_pages(5)

    assert first == {"parsed": b"payload"}
    assert second == first
    assert len(loader.session.calls) == 1


def test_get_title_details_uses_cache(monkeypatch):
    api.APILoaderMixin._get_title_details.cache_clear()
    loader = DummyLoader()

    monkeypatch.setattr(api, "_parse_title_detail_response", lambda content: {"parsed": content})

    first = loader._get_title_details(77)
    second = loader._get_title_details(77)

    assert first == {"parsed": b"payload"}
    assert second == first
    assert len(loader.session.calls) == 1


def test_title_detail_url():
    loader = DummyLoader()
    assert loader._build_title_detail_url() == "https://api.example/api/title_detailV3"
