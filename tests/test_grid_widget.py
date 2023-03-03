from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

from pymmcore_plus import CMMCorePlus
from useq import GridFromEdges, GridRelative

from pymmcore_widgets._mda import GridWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_mda_grid(qtbot: QtBot, global_mmcore: CMMCorePlus):
    grid_wdg = GridWidget()
    qtbot.addWidget(grid_wdg)

    global_mmcore.setProperty("Objective", "Label", "Objective-2")
    assert not global_mmcore.getPixelSizeUm()
    grid_wdg._update_info()
    assert (
        grid_wdg.info_lbl.text()
        == "Height: _ mm    Width: _ mm    (Rows: _    Columns: _)"
    )

    global_mmcore.setProperty("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    assert global_mmcore.getPixelSizeUm() == 0.5
    assert tuple(global_mmcore.getXYPosition()) == (0.0, 0.0)
    assert tuple(global_mmcore.getROI()) == (0, 0, 512, 512)

    grid_wdg.set_state(GridRelative(rows=2, columns=2))
    assert (
        grid_wdg.info_lbl.text()
        == "Height: 0.512 mm    Width: 0.512 mm    (Rows: 2    Columns: 2)"
    )

    mock = Mock()
    grid_wdg.valueChanged.connect(mock)

    grid_wdg._emit_grid_positions()

    mock.assert_has_calls([call(grid_wdg.value())])

    grid_wdg.set_state(
        GridFromEdges(top=256, bottom=-256, left=-256, right=256, overlap=(0.0, 50.0))
    )
    assert (
        grid_wdg.info_lbl.text()
        == "Height: 0.768 mm    Width: 0.768 mm    (Rows: 3    Columns: 3)"
    )

    grid_wdg._emit_grid_positions()

    mock.assert_has_calls([call(grid_wdg.value())])


def test_grid_set_and_get_state(qtbot: QtBot, global_mmcore: CMMCorePlus):
    grid_wdg = GridWidget()
    qtbot.addWidget(grid_wdg)

    grid_wdg.set_state(
        GridRelative(rows=3, columns=3, overlap=15.0, relative_to="top_left")
    )
    assert grid_wdg.value() == {
        "overlap": (15.0, 15.0),
        "mode": "row_wise_snake",
        "rows": 3,
        "columns": 3,
        "relative_to": "top_left",
    }
    assert grid_wdg.tab.currentIndex() == 0

    grid_wdg.set_state(
        GridFromEdges(top=512, bottom=-512, left=-512, right=512, mode="spiral")
    )
    assert grid_wdg.value() == {
        "overlap": (0.0, 0.0),
        "mode": "spiral",
        "top": 512.0,
        "bottom": -512.0,
        "left": -512.0,
        "right": 512.0,
    }
    assert grid_wdg.tab.currentIndex() == 1

    grid_wdg.set_state(
        {
            "overlap": (10.0, 0.0),
            "mode": "row_wise_snake",
            "top": 512.0,
            "bottom": -512.0,
            "left": -512.0,
            "right": 512.0,
        }
    )
    assert grid_wdg.value() == {
        "overlap": (10.0, 0.0),
        "mode": "row_wise_snake",
        "top": 512.0,
        "bottom": -512.0,
        "left": -512.0,
        "right": 512.0,
    }
    assert grid_wdg.tab.currentIndex() == 1


def test_grid_move_to(qtbot: QtBot, global_mmcore: CMMCorePlus):
    pass
