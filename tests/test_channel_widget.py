from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QComboBox

from pymmcore_widgets._channel_widget import ChannelWidget
from pymmcore_widgets._presets_widget import PresetsWidget
from pymmcore_widgets._util import block_core

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
        assert wdg.channel_wdg.count() == 0

    global_mmcore.setChannelGroup("Channel")
    assert isinstance(wdg.channel_wdg, PresetsWidget)
    assert len(wdg.channel_wdg.allowedValues()) == 4

    with qtbot.waitSignal(global_mmcore.events.presetDeleted):
        global_mmcore.deleteConfig("Channel", "DAPI")

    assert "DAPI" not in global_mmcore.getAvailableConfigs("Channel")
    assert "DAPI" not in wdg.channel_wdg.allowedValues()

    with qtbot.waitSignal(global_mmcore.events.groupDeleted):
        global_mmcore.deleteConfigGroup("Channel")
    assert isinstance(wdg.channel_wdg, QComboBox)
    assert wdg.channel_wdg.count() == 0
    assert global_mmcore.getChannelGroup() == ""

    with qtbot.waitSignal(global_mmcore.events.newGroupPreset):

        dev_prop_val = [
            ("Dichroic", "Label", "400DCLP"),
            ("Emission", "Label", "Chroma-HQ700"),
            ("Excitation", "Label", "Chroma-HQ570"),
        ]

        with block_core(global_mmcore.events):
            for d, p, v in dev_prop_val:
                global_mmcore.defineConfig("Channels", "DAPI", d, p, v)

        global_mmcore.events.newGroupPreset.emit("Channels", "DAPI", d, p, v)

    assert isinstance(wdg.channel_wdg, PresetsWidget)
    assert len(wdg.channel_wdg.allowedValues()) == 1
    assert global_mmcore.getChannelGroup() == "Channels"
