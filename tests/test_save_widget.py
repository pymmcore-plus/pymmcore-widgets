import pytest
from pytestqt.qtbot import QtBot

from pymmcore_widgets.mda._save_widget import FILE_NAME, SUBFOLDER, _SaveWidget

values = [
    ({"save_dir": "dir", "save_name": "name.ome.tiff", "format": "ome-tiff"}, ""),
    ({"save_dir": "dir", "save_name": "name", "format": "tiff-sequence"}, ""),
    ({"save_dir": "dir", "save_name": "name.ome.zarr", "format": "ome-zarr"}, ""),
    (
        {"save_dir": "dir", "save_name": "name.ome.tiff", "format": "ome-zarr"},
        "name.ome.zarr",
    ),
    (
        {"save_dir": "dir", "save_name": "name.png", "format": "ome-tiff"},
        "name.png.ome.tiff",
    ),
    (
        {"save_dir": "dir", "save_name": "name.ome.tif", "format": "ome-tiff"},
        "name.ome.tif",
    ),
]


@pytest.mark.skip
@pytest.mark.parametrize("value, name", values)
def test_set_get_value(qtbot: QtBot, value, name):
    wdg = _SaveWidget()
    qtbot.addWidget(wdg)

    assert not wdg.isChecked()
    assert wdg.value() == {"save_dir": "", "save_name": "", "format": "ome-zarr"}

    wdg.setValue(value)
    assert wdg.isChecked()
    assert wdg._writer_combo.currentText() == value["format"]
    if name:
        assert wdg.value()["save_name"] == name
    else:
        assert wdg.value() == value


INVALID_FORMAT = [
    {"save_dir": "dir", "save_name": "name", "format": "png"},
    {"save_dir": "dir", "save_name": "name", "format": ""},
    {"save_dir": "dir", "save_name": "name"},
]


@pytest.mark.skip
@pytest.mark.parametrize("value", INVALID_FORMAT)
def test_set_value_invalid_format(qtbot: QtBot, value):
    wdg = _SaveWidget()
    qtbot.addWidget(wdg)
    assert not wdg.isChecked()

    wdg._writer_combo.setCurrentText("ome-tiff")

    wdg.setValue(value)

    assert not wdg.isChecked()
    assert wdg.value() == {
        "save_dir": "dir",
        "save_name": "name",
        "format": "tiff-sequence",
    }


values = [
    ({"save_dir": "", "save_name": "", "format": "ome-zarr"}, False),
    ({"save_dir": "dir", "save_name": "", "format": "ome-zarr"}, False),
    ({"save_dir": "", "save_name": "name", "format": "ome-zarr"}, False),
    ({"save_dir": "dir", "save_name": "name", "format": "ome-zarr"}, True),
]


@pytest.mark.skip
@pytest.mark.parametrize("value, checked", values)
def test_groupbox_checked(qtbot: QtBot, value, checked):
    wdg = _SaveWidget()
    qtbot.addWidget(wdg)

    assert not wdg.isChecked()
    wdg.setValue(value)
    assert wdg.isChecked() == checked


writers = [
    ("ome-zarr", ".ome.zarr", FILE_NAME),
    ("ome-tiff", ".ome.tiff", FILE_NAME),
    ("tiff-sequence", "", SUBFOLDER),
]


@pytest.mark.parametrize("writer, ext, label", writers)
def test_writer_combo_text_changed(qtbot: QtBot, writer, ext, label):
    wdg = _SaveWidget()
    qtbot.addWidget(wdg)

    wdg.setValue({"save_dir": "dir", "save_name": "name", "format": "ome-tiff"})

    wdg._writer_combo.setCurrentText(writer)
    assert wdg._writer_combo.currentText() == writer
    assert wdg.name_label.text() == label
    assert wdg.save_name.text() == f"name{ext}"
