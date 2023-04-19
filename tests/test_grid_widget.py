from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

from pymmcore_plus import CMMCorePlus
from useq import GridFromEdges, GridRelative
from useq._grid import OrderMode, RelativeTo

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

    grid_wdg.set_state({"rows": 2, "columns": 2})
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
        {"rows": 3, "columns": 3, "overlap": 15.0, "relative_to": "top_left"}
    )
    assert grid_wdg.value() == {
        "overlap": (15.0, 15.0),
        "mode": "row_wise_snake",
        "rows": 3,
        "columns": 3,
        "relative_to": "top_left",
    }
    assert grid_wdg.tab.currentIndex() == 0

    # using RelativeTo enum
    grid_wdg.set_state(
        {"rows": 3, "columns": 3, "overlap": 15.0, "relative_to": RelativeTo.top_left}
    )
    assert grid_wdg.value() == {
        "overlap": (15.0, 15.0),
        "mode": "row_wise_snake",
        "rows": 3,
        "columns": 3,
        "relative_to": "top_left",
    }
    assert grid_wdg.tab.currentIndex() == 0

    # using GridPlan (and not dict)
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

    # using OrderMode enum
    grid_wdg.set_state(
        {
            "overlap": (10.0, 0.0),
            # "mode": "row_wise_snake",
            "mode": OrderMode.row_wise_snake,
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


def test_grid_from_edges_set_button(qtbot: QtBot, global_mmcore: CMMCorePlus):
    grid_wdg = GridWidget()
    qtbot.addWidget(grid_wdg)
    mmc = global_mmcore

    assert grid_wdg.tab.edges.value() == {
        "top": 0.0,
        "bottom": 0.0,
        "left": 0.0,
        "right": 0.0,
    }

    mmc.setXYPosition(100.0, 200.0)
    grid_wdg.tab.edges.top.set_button.click()
    grid_wdg.tab.edges.left.set_button.click()
    assert grid_wdg.tab.edges.value() == {
        "top": 200.0,
        "bottom": 0.0,
        "left": 100.0,
        "right": 0.0,
    }


def test_grid_on_px_size_changed(qtbot: QtBot, global_mmcore: CMMCorePlus):
    grid_wdg = GridWidget()
    qtbot.addWidget(grid_wdg)
    mmc = global_mmcore

    assert mmc.getProperty("Objective", "Label") == "Nikon 10X S Fluor"
    assert mmc.getPixelSizeUm() == 1.0
    grid_wdg.set_state(GridRelative(rows=2, columns=2))
    assert (
        grid_wdg.info_lbl.text()
        == "Height: 1.024 mm    Width: 1.024 mm    (Rows: 2    Columns: 2)"
    )

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.setPixelSizeUm("Res10x", 0.5)
    assert (
        grid_wdg.info_lbl.text()
        == "Height: 0.512 mm    Width: 0.512 mm    (Rows: 2    Columns: 2)"
    )

    grid_wdg._disconnect()
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.setPixelSizeUm("Res10x", 1)
    assert (
        grid_wdg.info_lbl.text()
        == "Height: 0.512 mm    Width: 0.512 mm    (Rows: 2    Columns: 2)"
    )


def test_grid_move_to(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    mmc.setXYPosition(100.0, 100.0)

    grid_wdg = GridWidget(current_stage_pos=(mmc.getXPosition(), mmc.getYPosition()))
    qtbot.addWidget(grid_wdg)
    _move = grid_wdg.move_to

    curr_x, curr_y = grid_wdg._current_stage_pos
    assert round(curr_x) == 100
    assert round(curr_y) == 100

    grid_wdg.set_state(
        {"rows": 2, "columns": 2, "overlap": (0.0, 0.0), "mode": "row_wise"}
    )

    assert _move._move_to_row.currentText() == "1"
    assert _move._move_to_col.currentText() == "1"

    mmc.waitForSystem()
    _move._move_button.click()
    assert round(mmc.getXPosition()) == -156
    assert round(mmc.getYPosition()) == 356

    _move._move_to_row.setCurrentText("2")
    mmc.waitForSystem()
    _move._move_button.click()
    assert round(mmc.getXPosition()) == -156
    assert round(mmc.getYPosition()) == -156

    _move._move_to_col.setCurrentText("2")
    mmc.waitForSystem()
    _move._move_button.click()
    assert round(mmc.getXPosition()) == 356
    assert round(mmc.getYPosition()) == -156

    grid_wdg.set_state({"top": 512, "bottom": 0, "left": 512, "right": 0})

    assert _move._move_to_row.currentText() == "1"
    assert _move._move_to_col.currentText() == "1"

    mmc.waitForSystem()
    _move._move_button.click()
    assert round(mmc.getXPosition()) == 0
    assert round(mmc.getYPosition()) == 512

    _move._move_to_row.setCurrentText("2")
    _move._move_to_col.setCurrentText("2")

    mmc.waitForSystem()
    _move._move_button.click()
    assert round(mmc.getXPosition()) == 512
    assert round(mmc.getYPosition()) == 0
