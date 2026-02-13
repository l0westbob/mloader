from types import SimpleNamespace

from mloader.constants import Language
from mloader.exporters.exporter_base import ExporterBase, _is_extra


class DummyExporter(ExporterBase):
    format = "dummy"

    def add_image(self, image_data, index):
        self.last = (image_data, index)

    def skip_image(self, index):
        return False


def _title(name="demo title", language=Language.ENGLISH.value):
    return SimpleNamespace(name=name, language=language)


def _chapter(name="#1", sub_title="subtitle"):
    return SimpleNamespace(name=name, sub_title=sub_title)


def test_is_extra_detection():
    assert _is_extra("#Ex") is True
    assert _is_extra("#1") is False


def test_exporter_base_formats_prefix_suffix_and_page_names(tmp_path):
    exporter = DummyExporter(
        destination=str(tmp_path),
        title=_title(language=Language.FRENCH.value),
        chapter=_chapter(name="#12", sub_title=""),
    )

    assert "[FRENCH]" in exporter._chapter_prefix
    assert exporter._chapter_suffix == "- Unknown"
    assert exporter.format_page_name(2) == f"{exporter._chapter_prefix} - p002 - Unknown.jpg"
    assert exporter.format_page_name(range(1, 4), ext="png").endswith(".png")


def test_exporter_base_windows_path_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr("mloader.exporters.exporter_base.is_windows", lambda: True)

    exporter = DummyExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())

    assert exporter.destination.startswith("\\\\?\\")


def test_exporter_base_registers_subclasses_and_close_pass(tmp_path):
    exporter = DummyExporter(destination=str(tmp_path), title=_title(), chapter=_chapter())
    exporter.close()

    assert ExporterBase.FORMAT_REGISTRY["dummy"] is DummyExporter


def test_abstract_base_methods_have_noop_defaults():
    ExporterBase.add_image(None, b"", 0)
    ExporterBase.skip_image(None, 0)
    assert ExporterBase.format.fget(None) is None
