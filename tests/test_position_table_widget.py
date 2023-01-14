from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._mda import PositionTable

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_add_single_position(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    mmc = global_mmcore
    tb = p._table

    assert not tb.rowCount()
    p.setChecked(True)

    p.add_button.click()
    p.add_button.click()

    assert tb.rowCount() == 2

    for row in range(tb.rowCount()):
        name = f"Pos{row:03d}"
        assert tb.item(row, 0).text() == name
        assert tb.item(row, 0).toolTip() == name
        assert tb.item(row, 0).data(p.POS_ROLE) == name
        assert tb.cellWidget(row, 1).value() == 0.0
        assert tb.cellWidget(row, 2).value() == 0.0
        assert tb.cellWidget(row, 3).value() == 0.0

    tb.item(row, 0).setText("test000")
    assert tb.item(row, 0).text() == "test000"
    assert tb.item(row, 0).toolTip() == name
    assert tb.item(row, 0).data(p.POS_ROLE) == name

    mmc.unloadDevice("XY")

    p.clear_button.click()
    assert not tb.rowCount()

    p.add_button.click()

    name = "Pos000"
    assert tb.item(0, 0).text() == name
    assert tb.item(0, 0).toolTip() == name
    assert tb.item(0, 0).data(p.POS_ROLE) == name
    assert not tb.cellWidget(0, 1)
    assert not tb.cellWidget(0, 2)
    assert tb.cellWidget(0, 3).value() == 0.0

    mmc.loadSystemConfiguration()
    mmc.unloadDevice("Z")

    p.clear_button.click()
    assert not tb.rowCount()

    p.add_button.click()

    assert tb.item(0, 0).text() == name
    assert tb.item(0, 0).toolTip() == name
    assert tb.item(0, 0).data(p.POS_ROLE) == name
    assert tb.cellWidget(0, 1).value() == 0.0
    assert tb.cellWidget(0, 2).value() == 0.0
    assert not tb.cellWidget(0, 3)


def test_rename_single_pos_after_delete(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    tb = p._table

    assert not tb.rowCount()
    p.setChecked(True)

    p.add_button.click()
    p.add_button.click()
    p.add_button.click()

    assert tb.rowCount() == 3

    assert tb.item(0, 0).text() == "Pos000"
    assert tb.item(1, 0).text() == "Pos001"
    assert tb.item(2, 0).text() == "Pos002"

    tb.selectRow(1)
    p.remove_button.click()

    assert tb.rowCount() == 2

    assert tb.item(0, 0).text() == "Pos000"
    assert tb.item(1, 0).text() == "Pos001"

    p.add_button.click()
    assert tb.item(2, 0).text() == "Pos002"

    tb.item(1, 0).setText("test")

    tb.selectRow(0)
    p.remove_button.click()

    assert tb.item(0, 0).text() == "test"
    assert tb.item(0, 0).toolTip() == "Pos000"
    assert tb.item(0, 0).data(p.POS_ROLE) == "Pos000"

    assert tb.item(1, 0).text() == "Pos001"


def test_rename_grid_pos_after_delete(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    tb = p._table

    assert not tb.rowCount()
    p.setChecked(True)

    p.grid_button.click()
    p._grid_wdg.scan_size_spinBox_r.setValue(2)
    p._grid_wdg.clear_checkbox.setChecked(False)

    p._grid_wdg.generate_position_btn.click()

    assert tb.rowCount() == 2

    for row in range(tb.rowCount()):
        name = f"Grid000_Pos{row:03d}"
        assert tb.item(row, 0).text() == name
        assert tb.item(row, 0).toolTip() == name
        assert tb.item(row, 0).data(p.POS_ROLE) == name

    p._grid_wdg.generate_position_btn.click()
    p._grid_wdg.generate_position_btn.click()

    assert tb.rowCount() == 6

    tb.item(2, 0).setText("test")

    tb.selectRow(0)
    p.remove_button.click()

    assert tb.rowCount() == 4

    grid_n = 0
    pos = 0
    for row in range(tb.rowCount()):
        name = f"Grid{grid_n:03d}_Pos{pos:03d}"
        if row == 0:
            assert tb.item(row, 0).text() == "test"
        else:
            assert tb.item(row, 0).text() == name
        assert tb.item(row, 0).toolTip() == name
        assert tb.item(row, 0).data(p.POS_ROLE) == name
        pos += 1
        if row in {1, 3}:
            grid_n += 1
            pos = 0
