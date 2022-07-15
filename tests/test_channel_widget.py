from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QComboBox

from pymmcore_widgets._channel_widget import ChannelWidget
from pymmcore_widgets._presets_widget import PresetsWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_channel_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):

    wdg = ChannelWidget()
    qtbot.addWidget(wdg)

    assert global_mmcore.getChannelGroup() == "Channel"

    assert isinstance(wdg.channel_wdg, PresetsWidget)

    global_mmcore.setProperty("Core", "Shutter", "")
    assert not global_mmcore.getShutterDevice()

    wdg.channel_wdg.setValue("DAPI")
    assert global_mmcore.getCurrentConfig("Channel") == "DAPI"
    assert global_mmcore.getShutterDevice() == "Multi Shutter"

    global_mmcore.setConfig("Channel", "FITC")
    assert wdg.channel_wdg.value() == "FITC"

    global_mmcore.setProperty("Emission", "Label", "Chroma-HQ700")
    assert wdg.channel_wdg._combo.styleSheet() == "color: magenta;"

    with qtbot.waitSignal(global_mmcore.events.channelGroupChanged):
        global_mmcore.setChannelGroup("")
        assert isinstance(wdg.channel_wdg, QComboBox)
        assert not wdg.channel_wdg.count()

    # TODO: continue when we have delete group/preset signals
