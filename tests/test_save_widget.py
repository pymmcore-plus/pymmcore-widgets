from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from pymmcore_widgets.mda._save_widget import (
    OME_TIFF,
    OME_ZARR,
    TIFF_SEQ,
    WRITERS,
    SaveGroupBox,
)


def test_set_get_value(qtbot: QtBot) -> None:
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)

    # Can be set with a Path or a string, in which case `should_save` be set to True
    # without a known extension, the current writer is kept
    path = Path("/some_path/some_file")
    wdg.setValue(path)
    assert wdg.value() == {
        "save_dir": str(path.parent),
        "save_name": str(path.name),
        "should_save": True,
        "format": OME_ZARR,
    }

    # When setting to a file with an extension, the format is set to the known writer
    wdg.setValue("/some_path/some_file.ome.tif")
    assert wdg.value()["format"] == OME_TIFF

    # unrecognized extensions warn and keep the current writer
    with pytest.warns(
        UserWarning, match=f"Invalid format '.png'. Using the {OME_TIFF} writer."
    ):
        wdg.setValue("/some_path/some_file.png")
    assert wdg.value() == {
        "save_dir": str(path.parent),
        "save_name": "some_file.png",  # note, we don't change the name
        "should_save": True,
        "format": OME_TIFF,
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
    qtbot.waitUntil(lambda: wdg.save_name.text() == "name.ome.zarr")


@pytest.mark.parametrize("writer", WRITERS)
def test_writer_combo_text_changed(qtbot: QtBot, writer: str) -> None:
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)
    wdg._writer_combo.setCurrentText(writer)
    wdg.save_name.setText("name")
    wdg.save_name.editingFinished.emit()

    assert wdg._writer_combo.currentText() == writer
    qtbot.waitUntil(lambda: wdg.save_name.text() == f"name{WRITERS[writer][0]}")


def test_tiff_sequence_not_offered(qtbot: QtBot) -> None:
    """pymmcore-plus has no tiff-sequence writer for a path, so it is not offered."""
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)
    items = [wdg._writer_combo.itemText(i) for i in range(wdg._writer_combo.count())]
    assert items == list(WRITERS)
    assert TIFF_SEQ not in items


def test_set_value_legacy_tiff_sequence(qtbot: QtBot) -> None:
    """A saved sequence with the old tiff-sequence format still loads."""
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)
    with pytest.warns(UserWarning, match=f"Using the {OME_ZARR} writer"):
        wdg.setValue({"save_dir": "/some_path", "save_name": "exp", "format": TIFF_SEQ})
    assert wdg.value()["format"] == OME_ZARR
    assert wdg.value()["save_name"] == "exp.ome.zarr"


def test_set_value_legacy_tiff_sequence_ignores_current_writer(qtbot: QtBot) -> None:
    """The old format picks OME-Zarr, whatever writer the widget used before."""
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)
    wdg._writer_combo.setCurrentText(OME_TIFF)
    with pytest.warns(UserWarning, match=f"Using the {OME_ZARR} writer"):
        wdg.setValue({"save_dir": "/some_path", "save_name": "exp", "format": TIFF_SEQ})
    assert wdg.value()["format"] == OME_ZARR
    assert wdg.value()["save_name"] == "exp.ome.zarr"

    # a name with a known extension keeps its writer
    with pytest.warns(UserWarning, match=f"Using the {OME_TIFF} writer"):
        wdg.setValue(
            {"save_dir": "/some_path", "save_name": "exp.ome.tif", "format": TIFF_SEQ}
        )
    assert wdg.value()["format"] == OME_TIFF
    assert wdg.value()["save_name"] == "exp.ome.tif"


@pytest.mark.parametrize(
    ("name", "writer", "expected"),
    [
        ("exp.OME.TIF", OME_TIFF, "exp.ome.tif"),
        ("exp.Ome.Tiff", OME_TIFF, "exp.ome.tiff"),
        ("exp.OME.ZARR", OME_ZARR, "exp.ome.zarr"),
    ],
)
def test_extension_case_insensitive(
    qtbot: QtBot, name: str, writer: str, expected: str
) -> None:
    """Extensions are recognized in any case and shown as they are written."""
    wdg = SaveGroupBox()
    qtbot.addWidget(wdg)
    wdg._writer_combo.setCurrentText(OME_ZARR if writer == OME_TIFF else OME_TIFF)
    wdg.save_name.setText(name)
    wdg.save_name.editingFinished.emit()
    assert wdg._writer_combo.currentText() == writer
    assert wdg.save_name.text() == expected
