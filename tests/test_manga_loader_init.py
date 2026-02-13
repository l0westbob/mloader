from mloader.manga_loader.init import MangaLoader


def test_manga_loader_creates_independent_default_sessions():
    loader_a = MangaLoader(exporter=None, quality="high", split=False, meta=False)
    loader_b = MangaLoader(exporter=None, quality="high", split=False, meta=False)

    assert loader_a.session is not loader_b.session
    assert "User-Agent" in loader_a.session.headers
