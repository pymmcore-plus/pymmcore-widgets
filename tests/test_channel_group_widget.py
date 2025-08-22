from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import ChannelGroupWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_channel_group_widget(qtbot: QtBot):
    ch = ChannelGroupWidget()
    qtbot.addWidget(ch)
    mmc = ch._mmc

    assert mmc.getChannelGroup() == "Channel"
    assert ch.currentText() == "Channel"

    mmc.setProperty("Core", "ChannelGroup", "Camera")
    assert ch.currentText() == "Camera"
    assert mmc.getChannelGroup() == "Camera"

    mmc.setProperty("Core", "ChannelGroup", "")
    assert not mmc.getChannelGroup()
    assert ch.currentText() == "<no match>"

    mmc.setChannelGroup("Channel")
    assert ch.currentText() == "Channel"
    assert mmc.getChannelGroup() == "Channel"

    mmc.deleteConfigGroup("Channel")
    assert not mmc.getChannelGroup()
    assert ch.currentText() == "<no match>"
    assert "Channel" not in [ch.itemText(idx) for idx in range(ch.count())]

    mmc.defineConfig("test_group", "test_preset")
    assert "test_group" in [ch.itemText(idx) for idx in range(ch.count())]

    ch._disconnect()
    mmc.setProperty("Core", "ChannelGroup", "LightPath")
    assert ch.currentText() == "<no match>"
    assert mmc.getChannelGroup() == "LightPath"
