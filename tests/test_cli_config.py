import logging

from mloader.cli import config as cli_config


def test_setup_logging_calls_basic_config(monkeypatch):
    captured = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    cli_config.setup_logging()

    assert captured["level"] == logging.INFO
    assert captured["style"] == "{"
    assert isinstance(captured["handlers"][0], logging.StreamHandler)
    assert logging.getLogger("requests").level == logging.WARNING
    assert logging.getLogger("urllib3").level == logging.WARNING


def test_get_logger_returns_named_logger():
    logger = cli_config.get_logger("mloader.tests")
    assert logger.name == "mloader.tests"
