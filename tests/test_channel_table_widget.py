from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._mda import ChannelTable

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


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

    mmc.deleteConfig("Channel", "Cy5")
    assert ct._table.rowCount() == 3
    ch_combo_1 = ct._table.cellWidget(0, 0)
    assert ch_combo_1.currentText() == "DAPI"
    assert "Cy5" not in [ch_combo_1.itemText(idx) for idx in range(ch_combo_1.count())]

    ch_combo_2 = ct._table.cellWidget(1, 0)
    assert ch_combo_2.currentText() == "DAPI"
    assert "Cy5" not in [ch_combo_1.itemText(idx) for idx in range(ch_combo_2.count())]

    mmc.deleteConfigGroup("Channel")
    assert ct._table.rowCount() == 1
    assert ct._table.cellWidget(0, 0).currentText() == "HighRes"

    mmc.setProperty("Core", "ChannelGroup", "Camera")
    assert ct.channel_group_combo.currentText() == "Camera"
    assert global_mmcore.getChannelGroup() == "Camera"

    # TODO: add mmc.setChannelGroup() when we will implement a signal in pymmcore-plus
