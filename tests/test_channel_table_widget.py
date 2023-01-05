from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._mda import ChannelTable

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot
    from qtpy.QtWidgets import QComboBox


def get_combo_values(combo: QComboBox):
    return [combo.itemText(idx) for idx in range(combo.count())]


def test_channel_table_widget_btns(global_mmcore: CMMCorePlus, qtbot: QtBot):
    ct = ChannelTable()
    qtbot.addWidget(ct)

    assert ct.channel_group_combo.currentText() == "Channel"
    assert global_mmcore.getChannelGroup() == "Channel"

    ct._add_button.click()
    ct._add_button.click()
    assert ct._table.rowCount() == 2

    assert ct._table.cellWidget(0, 0).currentText() == "Cy5"
    assert ct._table.cellWidget(1, 0).currentText() == "DAPI"

    ct.channel_group_combo.setCurrentText("Camera")
    ct._add_button.click()
    assert ct._table.rowCount() == 3
    assert ct._table.cellWidget(2, 0).currentText() == "HighRes"

    ct._clear_button.click()
    assert not ct._table.rowCount()


def test_channel_table_widget_core_signals(global_mmcore: CMMCorePlus, qtbot: QtBot):
    ct = ChannelTable()
    qtbot.addWidget(ct)
    mmc = global_mmcore

    ct.set_state(
        [
            {"config": "Cy5", "group": "Channel", "exposure": 100.0},
            {"config": "DAPI", "group": "Channel", "exposure": 100.0},
            {"config": "HighRes", "group": "Camera", "exposure": 100.0},
        ]
    )

    assert ct._table.rowCount() == 3
    assert ct._table.cellWidget(0, 0).currentText() == "Cy5"
    assert ct._table.cellWidget(1, 0).currentText() == "DAPI"
    assert ct._table.cellWidget(2, 0).currentText() == "HighRes"

    assert ct.channel_group_combo.currentText() == "Channel"
    assert global_mmcore.getChannelGroup() == "Channel"

    mmc.setProperty("Core", "ChannelGroup", "Camera")
    assert ct.channel_group_combo.currentText() == "Camera"
    assert mmc.getChannelGroup() == "Camera"

    mmc.setProperty("Core", "ChannelGroup", "")
    assert not mmc.getChannelGroup()
    assert ct.channel_group_combo.currentText() == "Camera"
    assert ct.channel_group_combo.styleSheet() == "color: magenta;"

    mmc.setChannelGroup("Channel")
    assert ct.channel_group_combo.currentText() == "Channel"
    assert mmc.getChannelGroup() == "Channel"
    assert not ct.channel_group_combo.styleSheet()

    mmc.deleteConfig("Channel", "Cy5")
    assert ct._table.rowCount() == 3
    ch_combo_1 = ct._table.cellWidget(0, 0)
    assert ch_combo_1.currentText() == "DAPI"
    assert "Cy5" not in get_combo_values(ch_combo_1)

    ch_combo_2 = ct._table.cellWidget(1, 0)
    assert ch_combo_2.currentText() == "DAPI"
    assert "Cy5" not in get_combo_values(ch_combo_1)

    mmc.deleteConfigGroup("Channel")
    assert ct._table.rowCount() == 1
    assert ct._table.cellWidget(0, 0).currentText() == "HighRes"

    mmc.defineConfig("test_group", "test_preset")
    assert "test_group" in get_combo_values(ct.channel_group_combo)


def test_channel_table_widget_disconnected(global_mmcore: CMMCorePlus, qtbot: QtBot):
    ct = ChannelTable(connect_core=False)
    qtbot.addWidget(ct)
    mmc = global_mmcore

    combo_groups = get_combo_values(ct.channel_group_combo)

    assert combo_groups == list(mmc.getAvailableConfigGroups())

    assert mmc.getChannelGroup() == "Channel"

    ct.channel_group_combo.setCurrentText("Camera")
    assert ct.channel_group_combo.currentText() == "Camera"
    assert mmc.getChannelGroup() != "Camera"
    assert mmc.getChannelGroup() == "Channel"

    mmc.setProperty("Core", "ChannelGroup", "Objective")
    assert mmc.getChannelGroup() == "Objective"
    assert mmc.getChannelGroup() != "Camera"
    assert ct.channel_group_combo.currentText() == "Camera"

    mmc.setChannelGroup("LightPath")
    assert mmc.getChannelGroup() == "LightPath"
    assert ct.channel_group_combo.currentText() == "Camera"

    mmc.deleteConfigGroup("Channel")
    combo_groups = get_combo_values(ct.channel_group_combo)
    assert "Channel" in combo_groups

    mmc.defineConfig("new_group", "new_preset")
    combo_groups = get_combo_values(ct.channel_group_combo)
    assert "new_group" not in combo_groups
