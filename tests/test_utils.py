from mloader import utils


def test_contains_keywords_is_case_insensitive():
    assert utils._contains_keywords("One Shot story", ["one", "SHOT"]) is True
    assert utils._contains_keywords("only one", ["one", "shot"]) is False


def test_is_oneshot_detects_keywords_and_numbered_chapters():
    assert utils.is_oneshot("#12", "one shot") is False
    assert utils.is_oneshot("One shot special", "") is True
    assert utils.is_oneshot("Special", "A one shot finale") is True
    assert utils.is_oneshot("Special", "Finale") is False


def test_chapter_name_to_int_handles_invalid_names():
    assert utils.chapter_name_to_int("#42") == 42
    assert utils.chapter_name_to_int("abc") is None


def test_escape_path_normalizes_special_characters():
    assert utils.escape_path("  hello:/world!?  ") == "hello world"


def test_is_windows_checks_platform(monkeypatch):
    monkeypatch.setattr(utils.sys, "platform", "win32")
    assert utils.is_windows() is True

    monkeypatch.setattr(utils.sys, "platform", "linux")
    assert utils.is_windows() is False
