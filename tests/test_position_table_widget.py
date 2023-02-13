from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QTableWidget
from useq import GridFromEdges, GridRelative, MDASequence

from pymmcore_widgets._mda import PositionTable

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def _get_values(table: QTableWidget, row: int):
    return (
        table.item(row, 0).text(),
        table.cellWidget(row, 1).value(),
        table.cellWidget(row, 2).value(),
        table.cellWidget(row, 3).value(),
    )


def test_single_position(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    mmc = global_mmcore
    tb = p._table

    assert not tb.rowCount()
    p.setChecked(True)

    p.add_button.click()
    mmc.setXYPosition(100, 200)
    p.add_button.click()

    assert tb.rowCount() == 2

    assert _get_values(tb, 0) == ("Pos000", 0.0, 0.0, 0.0)
    assert _get_values(tb, 1) == ("Pos001", 100.0, 200.0, 0.0)

    assert tb.item(1, 0).text() == "Pos001"
    tb.item(0, 0).setText("test")
    assert tb.item(0, 0).text() == "test"
    assert tb.item(1, 0).text() == "Pos000"

    p.add_button.click()
    p.add_button.click()
    assert tb.item(2, 0).text() == "Pos001"
    assert tb.item(3, 0).text() == "Pos002"
    assert tb.rowCount() == 4

    tb.selectRow(2)
    p.remove_button.click()
    assert tb.rowCount() == 3
    assert tb.item(2, 0).text() == "Pos001"


def test_grid_position(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    tb = p._table

    assert not tb.rowCount()
    p.setChecked(True)

    p.grid_button.click()
    p._grid_wdg.tab.setCurrentIndex(0)
    p._grid_wdg.set_state({"rows": 2, "columns": 2, "mode": "row_wise"})

    p._grid_wdg.add_button.click()
    assert tb.rowCount() == 4
    for row in range(tb.rowCount()):
        assert tb.item(row, 0).toolTip() == (
            "overlap=(0.0, 0.0) mode=row_wise rows=2 columns=2 relative_to=center"
        )
    assert _get_values(tb, 0) == ("Pos000_000_000_0", -256.0, 256.0, 0.0)
    assert _get_values(tb, 1) == ("Pos000_000_001_1", 256.0, 256.0, 0.0)
    assert _get_values(tb, 2) == ("Pos000_001_000_2", -256.0, -256.0, 0.0)
    assert _get_values(tb, 3) == ("Pos000_001_001_3", 256.0, -256.0, 0.0)

    p._grid_wdg.tab.setCurrentIndex(1)
    p._grid_wdg.set_state(
        {"top": 0.0, "bottom": -512.0, "left": 0.0, "right": 512.0, "mode": "spiral"}
    )
    p._grid_wdg.add_button.click()
    assert tb.rowCount() == 8
    for row in range(4, tb.rowCount()):
        assert tb.item(row, 0).toolTip() == (
            "overlap=(0.0, 0.0) mode=spiral top=0.0 left=0.0 bottom=-512.0 right=512.0"
        )
    assert _get_values(tb, 4) == ("Pos001_000_000_0", 0.0, 0.0, 0.0)
    assert _get_values(tb, 5) == ("Pos001_000_001_1", 512.0, 0.0, 0.0)
    assert _get_values(tb, 6) == ("Pos001_001_001_2", 512.0, -512.0, 0.0)
    assert _get_values(tb, 7) == ("Pos001_001_000_3", 0.0, -512.0, 0.0)

    tb.selectRow(2)
    rows = {r.row() for r in tb.selectedIndexes()}
    assert rows == {0, 1, 2, 3}

    assert tb.item(4, 0).text() == "Pos001_000_000_0"
    for row in rows:
        tb.item(row, 0).setText(f"test{row}")
    assert tb.item(4, 0).text() == "Pos000_000_000_0"

    p.clear()
    assert not tb.rowCount()


_input = [
    (0, {"rows": 2, "columns": 2, "mode": "row_wise", "overlap": 5.0}),
    (0, GridRelative(rows=2, columns=2, mode="row_wise", overlap=5.0)),
    (1, {"top": 0.0, "bottom": -512.0, "left": 0.0, "right": 512.0, "mode": "spiral"}),
    (1, GridFromEdges(top=0.0, bottom=-512.0, left=0.0, right=512.0, mode="spiral")),
]

_output = [
    [
        {
            "name": "Pos000",
            "sequence": MDASequence(
                grid_plan=GridRelative(
                    overlap=(5.0, 5.0),
                    mode="row_wise",
                    rows=2,
                    columns=2,
                    relative_to="center",
                )
            ),
            "x": -0.0,
            "y": -0.0,
            "z": 0.0,
        }
    ],
    [
        {
            "name": "Pos000",
            "sequence": MDASequence(
                grid_plan=GridFromEdges(
                    overlap=(0.0, 0.0),
                    mode="spiral",
                    top=0.0,
                    bottom=-512.0,
                    left=0.0,
                    right=512.0,
                )
            ),
            "x": None,
            "y": None,
            "z": 0.0,
        }
    ],
]


def test_set_and_get_state(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)
    p.grid_button.click()
    for i in _input:
        idx, grid = i
        p._grid_wdg.tab.setCurrentIndex(1)
        p._grid_wdg.set_state(grid)
        p._grid_wdg._emit_grid_positions()
        assert p.value() == _output[idx]
        p.clear()

    pos = [
        {"name": "Pos000", "x": 0.0, "y": 0.0, "z": 0.0},
        {
            "name": "Pos001",
            "x": -10.0,
            "y": -20.0,
            "z": 30.0,
            "sequence": MDASequence(grid_plan=GridRelative(rows=2, columns=1)),
        },
    ]
    p.set_state(pos)
    assert p._table.rowCount() == 3
    assert _get_values(p._table, 0) == ("Pos000", 0.0, 0.0, 0.0)
    assert _get_values(p._table, 1) == ("Pos001_000_000_0", -10.0, 246.0, 30.0)
    assert _get_values(p._table, 2) == ("Pos001_001_000_1", -10.0, -266.0, 30.0)
