import importlib


def test_import_mloader_main_module():
    module = importlib.reload(importlib.import_module("mloader.main"))
    assert callable(module.main)


def test_import_mloader_dunder_main_module():
    module = importlib.reload(importlib.import_module("mloader.__main__"))
    assert callable(module.main)


def test_import_cli_init_module():
    module = importlib.reload(importlib.import_module("mloader.cli.init"))
    assert callable(module.main)
