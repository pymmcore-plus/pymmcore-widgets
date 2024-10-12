from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QSize

from pymmcore_widgets.control._live_button_widget import LiveButton

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_live_button_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    live_btn = LiveButton()

    qtbot.addWidget(live_btn)

    assert live_btn.text() == "Live"
    assert live_btn.iconSize() == QSize(30, 30)
    assert live_btn.icon_color_on == (0, 255, 0)
    assert live_btn.icon_color_off == "magenta"

    # test from direct mmcore signals
    with qtbot.waitSignal(global_mmcore.events.continuousSequenceAcquisitionStarted):
        global_mmcore.startContinuousSequenceAcquisition(0)
    assert live_btn.text() == "Stop"

    with qtbot.waitSignal(global_mmcore.events.sequenceAcquisitionStopped):
        global_mmcore.stopSequenceAcquisition()
    assert not global_mmcore.isSequenceRunning()
    assert live_btn.text() == "Live"

    # test when button is pressed
    with qtbot.waitSignal(global_mmcore.events.continuousSequenceAcquisitionStarted):
        live_btn.click()
    assert live_btn.text() == "Stop"
    assert global_mmcore.isSequenceRunning()

    with qtbot.waitSignal(global_mmcore.events.sequenceAcquisitionStopped):
        live_btn.click()
    assert not global_mmcore.isSequenceRunning()
    assert live_btn.text() == "Live"

    live_btn.icon_color_on = "Red"
    assert live_btn._icon_color_on == "Red"
    live_btn.icon_color_off = "Green"
    assert live_btn._icon_color_off == "Green"
    live_btn.button_text_on = "LIVE"
    assert live_btn.text() == "LIVE"
    live_btn.button_text_off = "STOP"
    global_mmcore.startContinuousSequenceAcquisition(0)
    assert live_btn.text() == "STOP"
    global_mmcore.stopSequenceAcquisition()
    assert live_btn.text() == "LIVE"
