from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, DeviceType

from pymmcore_widgets._mda import PositionTable

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_add_single_position(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    mmc = global_mmcore

    assert not p._table.rowCount()
    p.setChecked(True)

    p.add_button.click()
    p.add_button.click()

    assert p._table.rowCount() == 2

    for row in range(p._table.rowCount()):
        name = f"Pos{row:03d}"
        assert p._table.item(row, 0).text() == name
        assert p._table.item(row, 0).toolTip() == name
        assert p._table.item(row, 0).whatsThis() == name
        assert p._table.cellWidget(row, 1).value() == 0.0
        assert p._table.cellWidget(row, 2).value() == 0.0
        assert p._table.cellWidget(row, 3).value() == 0.0

    p._table.item(row, 0).setText("test000")
    assert p._table.item(row, 0).text() == "test000"
    assert p._table.item(row, 0).toolTip() == name
    assert p._table.item(row, 0).whatsThis() == name

    mmc.unloadDevice("XY")

    p.clear_button.click()
    assert not p._table.rowCount()

    p.add_button.click()

    name = "Pos000"
    assert p._table.item(0, 0).text() == name
    assert p._table.item(0, 0).toolTip() == name
    assert p._table.item(0, 0).whatsThis() == name
    assert not p._table.cellWidget(0, 1)
    assert not p._table.cellWidget(0, 2)
    assert p._table.cellWidget(0, 3).value() == 0.0

    mmc.loadSystemConfiguration()
    mmc.unloadDevice("Z")

    p.clear_button.click()
    assert not p._table.rowCount()

    p.add_button.click()

    assert p._table.item(0, 0).text() == name
    assert p._table.item(0, 0).toolTip() == name
    assert p._table.item(0, 0).whatsThis() == name
    assert p._table.cellWidget(0, 1).value() == 0.0
    assert p._table.cellWidget(0, 2).value() == 0.0
    assert not p._table.cellWidget(0, 3)


def test_rename_single_pos_after_delete(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    assert not p._table.rowCount()
    p.setChecked(True)

    p.add_button.click()
    p.add_button.click()
    p.add_button.click()

    assert p._table.rowCount() == 3

    assert p._table.item(0, 0).text() == "Pos000"
    assert p._table.item(1, 0).text() == "Pos001"
    assert p._table.item(2, 0).text() == "Pos002"

    p._table.selectRow(1)
    p.remove_button.click()

    assert p._table.rowCount() == 2

    assert p._table.item(0, 0).text() == "Pos000"
    assert p._table.item(1, 0).text() == "Pos001"

    p.add_button.click()
    assert p._table.item(2, 0).text() == "Pos002"

    p._table.item(1, 0).setText("test")

    p._table.selectRow(0)
    p.remove_button.click()

    assert p._table.item(0, 0).text() == "test"
    assert p._table.item(0, 0).toolTip() == "Pos000"
    assert p._table.item(0, 0).whatsThis() == "Pos000"

    assert p._table.item(1, 0).text() == "Pos001"


def test_rename_grid_pos_after_delete(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    assert not p._table.rowCount()
    p.setChecked(True)

    p.grid_button.click()
    p._grid_wdg.scan_size_spinBox_r.setValue(2)
    p._grid_wdg.clear_checkbox.setChecked(False)

    p._grid_wdg.generate_position_btn.click()

    assert p._table.rowCount() == 2

    for row in range(p._table.rowCount()):
        name = f"Grid000_Pos{row:03d}"
        assert p._table.item(row, 0).text() == name
        assert p._table.item(row, 0).toolTip() == name
        assert p._table.item(row, 0).whatsThis() == name

    p._grid_wdg.generate_position_btn.click()
    p._grid_wdg.generate_position_btn.click()

    assert p._table.rowCount() == 6

    p._table.item(2, 0).setText("test")

    p._table.selectRow(0)
    p.remove_button.click()

    assert p._table.rowCount() == 4

    grid_n = 0
    pos = 0
    for row in range(p._table.rowCount()):
        name = f"Grid{grid_n:03d}_Pos{pos:03d}"
        if row == 0:
            assert p._table.item(row, 0).text() == "test"
        else:
            assert p._table.item(row, 0).text() == name
        assert p._table.item(row, 0).toolTip() == name
        assert p._table.item(row, 0).whatsThis() == name
        pos += 1
        if row in {1, 3}:
            grid_n += 1
            pos = 0


def test_position_table(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    p.setChecked(True)
    mmc = global_mmcore

    assert [
        p._table.horizontalHeaderItem(i).text() for i in range(p._table.columnCount())
    ] == [
        "Pos",
        "X",
        "Y",
        "Z",
        "Z1",
    ]
    assert len(mmc.getLoadedDevicesOfType(DeviceType.Stage)) == 2
    assert ["Z", "Z1"] == list(mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
    assert mmc.getFocusDevice() == "Z"

    assert p.z_stage_combo.currentText() == "Z"

    assert not p._table.isColumnHidden(3)  # "Z"
    assert p._table.isColumnHidden(4)  # "Z1"

    p.z_stage_combo.setCurrentText("Z1")
    assert mmc.getFocusDevice() == "Z1"
    assert p._table.isColumnHidden(3)  # "Z"
    assert not p._table.isColumnHidden(4)  # "Z1"

    mmc.unloadDevice("XY")
    p.z_stage_combo.setCurrentText("None")
    for c in range(p._table.columnCount()):
        assert p._table.isColumnHidden(c)

    p.z_stage_combo.setCurrentText("Z")
    assert p._table.columnCount() == 5

    assert p._table.horizontalHeaderItem(0).text() == "Pos"
    assert p._table.horizontalHeaderItem(3).text() == "Z"
    for c in range(p._table.columnCount()):
        if c in {0, 3}:
            assert not p._table.isColumnHidden(c)
        else:
            assert p._table.isColumnHidden(c)
