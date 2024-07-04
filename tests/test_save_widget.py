from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from pymmcore_widgets.mda._save_widget import (
    DIRECTORY_WRITERS,
    FILE_NAME,
    OME_TIFF,
    OME_ZARR,
    SUBFOLDER,
    TIFF_SEQ,
    WRITERS,
    SaveGroupBox,
)


def test_set_get_value(qtbot: QtBot) -> None:
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)

    # Can be set with a Path or a string, in which case `should_save` be set to True
    path = Path("/some_path/some_file")
    wdg.setValue(path)
    assert wdg.value() == {
        "save_dir": str(path.parent),
        "save_name": str(path.name),
        "should_save": True,
        "format": TIFF_SEQ,
    }

    # When setting to a file with an extension, the format is set to the known writer
    wdg.setValue("/some_path/some_file.ome.tif")
    assert wdg.value()["format"] == OME_TIFF

    # unrecognized extensions warn and default to TIFF_SEQ
    with pytest.warns(
        UserWarning, match=f"Invalid format '.png'. Defaulting to {TIFF_SEQ}."
    ):
        wdg.setValue("/some_path/some_file.png")
    assert wdg.value() == {
        "save_dir": str(path.parent),
        "save_name": "some_file.png",  # note, we don't change the name
        "should_save": True,
        "format": TIFF_SEQ,
    }

    # Can be set with a dict.
    # note that when setting with a dict, should_save must be set explicitly
    wdg.setValue({"save_dir": str(path.parent), "save_name": "some_file.ome.zarr"})
    assert wdg.value() == {
        "save_dir": str(path.parent),
        "save_name": "some_file.ome.zarr",
        "should_save": False,
        "format": OME_ZARR,
    }


def test_save_box_autowriter_selection(qtbot: QtBot) -> None:
    """Test that setting the name to known extension changes the format"""
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)

    wdg.save_name.setText("name.ome.tiff")
    wdg.save_name.editingFinished.emit()  # this only happens in the GUI
    assert wdg._writer_combo.currentText() == OME_TIFF

    # and it goes both ways
    wdg._writer_combo.setCurrentText(OME_ZARR)
    assert wdg.save_name.text() == "name.ome.zarr"


@pytest.mark.parametrize("writer", WRITERS)
def test_writer_combo_text_changed(qtbot: QtBot, writer: str) -> None:
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)
    wdg._writer_combo.setCurrentText(writer)
    wdg.save_name.setText("name")
    wdg.save_name.editingFinished.emit()

    assert wdg._writer_combo.currentText() == writer
    expected_label = SUBFOLDER if writer in DIRECTORY_WRITERS else FILE_NAME
    assert wdg.name_label.text() == expected_label
    assert wdg.save_name.text() == f"name{WRITERS[writer][0]}"
