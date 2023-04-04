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


def test_go_to_pos(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    mmc = global_mmcore
    tb = p._table

    mmc.setXYPosition(100, 200)
    mmc.setPosition(50)
    p.add_button.click()
    assert p._table.item(0, 0).text() == "Pos000"
    assert p._table.cellWidget(0, 1).value() == 100.0
    assert p._table.cellWidget(0, 2).value() == 200.0
    assert p._table.cellWidget(0, 3).value() == 50.0
    assert round(mmc.getXPosition()) == 100.0
    assert round(mmc.getYPosition()) == 200.0
    assert round(mmc.getPosition()) == 50.0

    mmc.waitForSystem()
    mmc.setXYPosition(0.0, 0.0)
    mmc.setPosition(0.0)
    assert mmc.getXPosition() == 0.0
    assert mmc.getYPosition() == 0.0
    assert mmc.getPosition() == 0.0

    tb.selectRow(0)
    mmc.waitForSystem()
    p.go_button.click()

    assert round(mmc.getXPosition()) == 100.0
    assert round(mmc.getYPosition()) == 200.0
    assert round(mmc.getPosition()) == 50.0


def test_pos_table_set_and_get_state(global_mmcore: CMMCorePlus, qtbot: QtBot):
    pos_1 = {"name": "Pos000", "x": 100.0, "y": 200.0, "z": 0.0}
    pos_2 = {"name": "Pos001", "x": 10.0, "y": 20.0, "z": 0.0}
    pos_3 = {"name": "Pos002", "x": 0.0, "y": 0.0, "z": 0.0}

    p = PositionTable()
    qtbot.addWidget(p)
    p.set_state([pos_1, pos_2, pos_3])
    assert p.value() == [pos_1, pos_2, pos_3]


def test_columns_position_table(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    p.setChecked(True)
    mmc = global_mmcore

    assert [
        p._table.horizontalHeaderItem(i).text() for i in range(p._table.columnCount())
    ] == ["Pos", "X", "Y", "Z", "Z1"]
    assert len(mmc.getLoadedDevicesOfType(DeviceType.Stage)) == 2
    assert ["Z", "Z1"] == list(mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
    assert mmc.getFocusDevice() == "Z"

    assert p.z_focus_combo.currentText() == "Z"
    assert p.get_used_z_stages() == {"Z Focus": "Z", "Z AutoFocus": ""}

    assert not p._table.isColumnHidden(3)  # "Z"
    assert p._table.isColumnHidden(4)  # "Z1"

    p.z_focus_combo.setCurrentText("Z1")
    assert p._table.isColumnHidden(3)  # "Z"
    assert not p._table.isColumnHidden(4)  # "Z1"
    assert p.get_used_z_stages() == {"Z Focus": "Z1", "Z AutoFocus": ""}

    mmc.unloadDevice("XY")
    p.z_focus_combo.setCurrentText("None")
    for c in range(1, p._table.columnCount() - 1):
        assert p._table.isColumnHidden(c)

    p.z_focus_combo.setCurrentText("Z")
    assert p._table.columnCount() == 5

    assert p._table.horizontalHeaderItem(0).text() == "Pos"
    assert p._table.horizontalHeaderItem(3).text() == "Z"
    for c in range(p._table.columnCount() - 1):
        if c in {0, 3}:
            assert not p._table.isColumnHidden(c)
        else:
            assert p._table.isColumnHidden(c)


def test_z_autofocus_combo(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    p.setChecked(True)
    mmc = global_mmcore

    assert p.z_autofocus_combo.currentText() == "None"
    assert mmc.getFocusDevice() == "Z"
    assert mmc.getAutoFocusDevice() == "Autofocus"
    assert not p._table.isColumnHidden(3)  # "Z"
    assert p._table.isColumnHidden(4)  # "Z1"
    assert p.get_used_z_stages() == {"Z Focus": "Z", "Z AutoFocus": ""}

    p.z_autofocus_combo.setCurrentText("Z1")
    assert p._table.isColumnHidden(3)  # "Z"
    assert not p._table.isColumnHidden(4)  # "Z1"
    assert p.get_used_z_stages() == {"Z Focus": "Z", "Z AutoFocus": "Z1"}

    p.z_focus_combo.setCurrentText("None")
    assert p._table.isColumnHidden(3)  # "Z"
    assert not p._table.isColumnHidden(4)  # "Z1"
    assert p.get_used_z_stages() == {"Z Focus": "", "Z AutoFocus": "Z1"}

    p.z_autofocus_combo.setCurrentText("None")
    assert p._table.isColumnHidden(3)  # "Z"
    assert p._table.isColumnHidden(4)  # "Z1"
    assert p.get_used_z_stages() == {"Z Focus": "", "Z AutoFocus": ""}
