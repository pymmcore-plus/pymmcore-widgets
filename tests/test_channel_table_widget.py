from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QComboBox

from pymmcore_widgets._mda import ChannelTable

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def _values(combo: QComboBox) -> list:
    return [combo.itemText(i) for i in range(combo.count())]


def test_channel_table_widget(qtbot: QtBot):
    ct = ChannelTable(channel_group="Camera")
    qtbot.addWidget(ct)

    assert ct.channel_group_combo.currentText() == "Camera"
    assert ct._mmc.getChannelGroup() == "Channel"

    ct.channel_group_combo.setCurrentText("Channel")

    ct._add_button.click()
    ct._add_button.click()
    assert ct._table.rowCount() == 2

    assert ct._table.cellWidget(0, 0).currentText() == "Cy5"
    assert ct._table.cellWidget(1, 0).currentText() == "DAPI"
    assert ct._table.cellWidget(1, 0).itemData(0, ct.CH_GROUP_ROLE) == "Channel"

    with qtbot.waitSignal(ct._mmc.events.configDeleted):
        ct._mmc.deleteConfig("Channel", "DAPI")
    assert ct._table.rowCount() == 2
    assert "DAPI" not in _values(ct._table.cellWidget(0, 0))
    assert "DAPI" not in _values(ct._table.cellWidget(1, 0))

    ct.channel_group_combo.setCurrentText("Camera")
    ct._add_button.click()
    assert ct._table.rowCount() == 3
    assert ct._table.cellWidget(2, 0).currentText() == "HighRes"
    assert ct._table.cellWidget(2, 0).itemData(0, ct.CH_GROUP_ROLE) == "Camera"

    with qtbot.waitSignal(ct._mmc.events.configGroupDeleted):
        ct._mmc.deleteConfigGroup("Channel")
    assert "Channel" not in _values(ct.channel_group_combo)
    assert ct._table.rowCount() == 1

    ct._clear_button.click()
    assert not ct._table.rowCount()


def test_set_get_state(qtbot: QtBot):
    ct = ChannelTable(channel_group="Camera")
    qtbot.addWidget(ct)

    state = [
        {"config": "Cy5", "group": "Channel", "exposure": 100.0},
        {"config": "DAPI", "group": "Channel", "exposure": 100.0},
        {"config": "HighRes", "group": "Camera", "exposure": 100.0},
    ]

    ct.set_state(state)

    assert ct._table.rowCount() == 3
    assert ct._table.cellWidget(0, 0).currentText() == "Cy5"
    assert ct._table.cellWidget(1, 0).currentText() == "DAPI"
    assert ct._table.cellWidget(2, 0).currentText() == "HighRes"

    assert ct.value() == state
