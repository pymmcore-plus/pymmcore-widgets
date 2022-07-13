from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets._shutter_widget import ShuttersWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_shutter_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):

    shutter = ShuttersWidget("Shutter", autoshutter=False)
    shutter.button_text_open = "Shutter opened"
    shutter.button_text_closed = "Shutter closed"
    qtbot.addWidget(shutter)
    shutter._refresh_shutter_widget()

    multi_shutter = ShuttersWidget("Multi Shutter")
    multi_shutter.button_text_open = "Multi Shutter opened"
    multi_shutter.button_text_closed = "Multi Shutter closed"
    qtbot.addWidget(multi_shutter)
    multi_shutter._refresh_shutter_widget()

    assert shutter.shutter_button.text() == "Shutter closed"
    assert not shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.text() == "Multi Shutter closed"
    assert multi_shutter.autoshutter_checkbox.isChecked()
    assert not multi_shutter.shutter_button.isEnabled()

    # test shutter change from core
    with qtbot.waitSignal(global_mmcore.events.propertyChanged):
        global_mmcore.setProperty("Shutter", "State", True)
        assert not shutter.shutter_button.isEnabled()
        assert global_mmcore.getShutterOpen("Shutter")
        assert shutter.shutter_button.text() == "Shutter opened"
        assert global_mmcore.getProperty("Shutter", "State") == "1"
        assert not multi_shutter.shutter_button.isEnabled()
        assert not global_mmcore.getShutterOpen("Multi Shutter")
        assert multi_shutter.shutter_button.text() == "Multi Shutter closed"
        assert global_mmcore.getProperty("Multi Shutter", "State") == "0"

    with qtbot.waitSignal(global_mmcore.events.autoShutterSet):
        global_mmcore.setAutoShutter(False)
        assert shutter.shutter_button.isEnabled()
        assert multi_shutter.shutter_button.isEnabled()
        global_mmcore.setAutoShutter(True)
        assert not shutter.shutter_button.isEnabled()
        assert not multi_shutter.shutter_button.isEnabled()

    with qtbot.waitSignals(
        [
            global_mmcore.events.configSet,
            global_mmcore.events.propertyChanged,
        ]
    ):
        global_mmcore.setConfig("Channel", "DAPI")
        global_mmcore.setShutterOpen("Multi Shutter", True)
        assert multi_shutter.shutter_button.text() == "Multi Shutter opened"
        assert global_mmcore.getProperty("Multi Shutter", "State") == "1"
        assert shutter.shutter_button.text() == "Shutter opened"
        assert global_mmcore.getProperty("Shutter", "State") == "1"

    with qtbot.waitSignals(
        [
            global_mmcore.events.startContinuousSequenceAcquisition,
            global_mmcore.events.propertyChanged,
            global_mmcore.events.stopSequenceAcquisition,
        ]
    ):
        global_mmcore.setConfig("Channel", "DAPI")
        global_mmcore.startContinuousSequenceAcquisition()
        assert multi_shutter.shutter_button.text() == "Multi Shutter opened"
        assert not multi_shutter.shutter_button.isEnabled()
        assert shutter.shutter_button.text() == "Shutter opened"
        assert not shutter.shutter_button.isEnabled()

        global_mmcore.setAutoShutter(False)
        assert shutter.shutter_button.isEnabled()
        assert multi_shutter.shutter_button.isEnabled()
        assert multi_shutter.shutter_button.text() == "Multi Shutter opened"
        assert shutter.shutter_button.text() == "Shutter opened"

        global_mmcore.stopSequenceAcquisition()
        assert shutter.shutter_button.isEnabled()
        assert multi_shutter.shutter_button.isEnabled()
        assert multi_shutter.shutter_button.text() == "Multi Shutter closed"
        assert shutter.shutter_button.text() == "Shutter closed"

    # test shutters change from shutter buttons
    with qtbot.waitSignal(global_mmcore.events.autoShutterSet):
        multi_shutter.autoshutter_checkbox.setChecked(True)
        assert not shutter.shutter_button.isEnabled()
        assert not multi_shutter.shutter_button.isEnabled()
        multi_shutter.autoshutter_checkbox.setChecked(False)
        assert shutter.shutter_button.isEnabled()
        assert multi_shutter.shutter_button.isEnabled()

    with qtbot.waitSignal(global_mmcore.events.propertyChanged):
        shutter.shutter_button.click()
        assert shutter.shutter_button.text() == "Shutter opened"
        assert global_mmcore.getShutterOpen("Shutter")
        assert global_mmcore.getProperty("Shutter", "State") == "1"
        shutter.shutter_button.click()
        assert shutter.shutter_button.text() == "Shutter closed"
        assert not global_mmcore.getShutterOpen("Shutter")
        assert global_mmcore.getProperty("Shutter", "State") == "0"

        multi_shutter.shutter_button.click()
        assert multi_shutter.shutter_button.text() == "Multi Shutter opened"
        assert global_mmcore.getShutterOpen("Multi Shutter")
        assert global_mmcore.getProperty("Multi Shutter", "State") == "1"
        assert shutter.shutter_button.text() == "Shutter opened"
        assert global_mmcore.getShutterOpen("Shutter")
        assert global_mmcore.getProperty("Shutter", "State") == "1"

    assert shutter.icon_size == 25
    shutter.icon_size = 30
    assert shutter.icon_size == 30

    assert shutter.icon_color_open == (0, 255, 0)
    shutter.icon_color_open = "magenta"
    assert shutter.icon_color_open == "magenta"

    assert shutter.icon_color_closed == "magenta"
    shutter.icon_color_closed = (0, 255, 0)
    assert shutter.icon_color_closed == (0, 255, 0)

    assert shutter.button_text_open == "Shutter opened"
    shutter.button_text_open = "O"
    assert shutter.button_text_open == "O"

    assert shutter.button_text_closed == "Shutter closed"
    shutter.button_text_closed = "C"
    assert shutter.button_text_closed == "C"

    global_mmcore.startContinuousSequenceAcquisition()
    assert shutter.shutter_button.text() == "O"
    global_mmcore.stopSequenceAcquisition()
    assert shutter.shutter_button.text() == "C"
