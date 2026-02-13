from click.testing import CliRunner

from mloader.cli import main as cli_main


class DummyLoader:
    init_args = None
    download_args = None

    def __init__(self, exporter_factory, quality, split, meta):
        type(self).init_args = {
            "exporter_factory": exporter_factory,
            "quality": quality,
            "split": split,
            "meta": meta,
        }

    def download(self, **kwargs):
        type(self).download_args = kwargs


class DummyRawExporter:
    pass


class DummyPdfExporter:
    pass


class FailingLoader(DummyLoader):
    def download(self, **kwargs):
        raise RuntimeError("boom")


def test_cli_uses_raw_exporter_when_raw_flag_is_set(monkeypatch):
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)
    monkeypatch.setattr(cli_main, "RawExporter", DummyRawExporter)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "123", "--raw"]) 

    assert result.exit_code == 0
    assert DummyLoader.init_args["exporter_factory"].func is DummyRawExporter
    assert DummyLoader.download_args["chapter_ids"] == {123}


def test_cli_uses_pdf_exporter_when_requested(monkeypatch):
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)
    monkeypatch.setattr(cli_main, "PDFExporter", DummyPdfExporter)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "55", "--format", "pdf"]) 

    assert result.exit_code == 0
    assert DummyLoader.init_args["exporter_factory"].func is DummyPdfExporter
    assert DummyLoader.download_args["chapter_ids"] == {55}


def test_cli_returns_error_when_download_fails(monkeypatch):
    monkeypatch.setattr(cli_main, "MangaLoader", FailingLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "55"])

    assert result.exit_code != 0
    assert "Download failed" in result.output


def test_cli_without_ids_prints_help_and_exits_cleanly():
    runner = CliRunner()
    result = runner.invoke(cli_main.main, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output
