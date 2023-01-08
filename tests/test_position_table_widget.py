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
    tb = p.stage_tableWidget

    assert not tb.rowCount()
    p.setChecked(True)

    p.add_button.click()
    p.add_button.click()

    assert tb.rowCount() == 2

    for row in range(tb.rowCount()):
        name = f"Pos{row:03d}"
        assert tb.item(row, 0).text() == name
        assert tb.item(row, 0).toolTip() == name
        assert tb.item(row, 0).whatsThis() == name
        assert tb.cellWidget(row, 1).value() == 0.0
        assert tb.cellWidget(row, 2).value() == 0.0
        assert tb.cellWidget(row, 3).value() == 0.0

    tb.item(row, 0).setText("test000")
    assert tb.item(row, 0).text() == "test000"
    assert tb.item(row, 0).toolTip() == name
    assert tb.item(row, 0).whatsThis() == name

    mmc.unloadDevice("XY")

    p.clear_button.click()
    assert not tb.rowCount()

    p.add_button.click()

    name = "Pos000"
    assert tb.item(0, 0).text() == name
    assert tb.item(0, 0).toolTip() == name
    assert tb.item(0, 0).whatsThis() == name
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
    assert tb.item(0, 0).whatsThis() == name
    assert tb.cellWidget(0, 1).value() == 0.0
    assert tb.cellWidget(0, 2).value() == 0.0
    assert not tb.cellWidget(0, 3)


def test_rename_single_pos_after_delete(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    tb = p.stage_tableWidget

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
    assert tb.item(0, 0).whatsThis() == "Pos000"

    assert tb.item(1, 0).text() == "Pos001"


def test_rename_grid_pos_after_delete(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    tb = p.stage_tableWidget

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
        assert tb.item(row, 0).whatsThis() == name

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
        assert tb.item(row, 0).whatsThis() == name
        pos += 1
        if row in {1, 3}:
            grid_n += 1
            pos = 0


def test_position_table(global_mmcore: CMMCorePlus, qtbot: QtBot):
    p = PositionTable()
    qtbot.addWidget(p)

    p.setChecked(True)
    mmc = global_mmcore
    tb = p.stage_tableWidget

    assert [tb.horizontalHeaderItem(i).text() for i in range(tb.columnCount())] == [
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

    assert not tb.isColumnHidden(3)  # "Z"
    assert tb.isColumnHidden(4)  # "Z1"

    p.z_stage_combo.setCurrentText("Z1")
    assert mmc.getFocusDevice() == "Z1"
    assert not tb.isColumnHidden(4)  # "Z1"
    assert tb.isColumnHidden(3)  # "Z"

    mmc.unloadDevice("XY")
    p.z_stage_combo.setCurrentText("None")
    for c in range(tb.columnCount()):
        assert tb.isColumnHidden(c)

    p.z_stage_combo.setCurrentText("Z")
    assert tb.columnCount() == 5

    assert tb.horizontalHeaderItem(0).text() == "Pos"
    assert tb.horizontalHeaderItem(3).text() == "Z"
    for c in range(tb.columnCount()):
        if c in {0, 3}:
            assert not tb.isColumnHidden(c)
        else:
            assert tb.isColumnHidden(c)
