from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pymmcore_widgets.control._shutter_widget import GRAY, GREEN, ShuttersWidget
from tests._utils import wait_signal

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def _make_shutters(
    qtbot: QtBot,
) -> tuple[ShuttersWidget, ShuttersWidget, ShuttersWidget]:
    _shutters = []
    for name, auto in [
        ("Shutter", False),
        ("StateDev Shutter", False),
        ("Multi Shutter", True),
    ]:
        shutter = ShuttersWidget(name, autoshutter=auto)
        shutter.button_text_open = f"{name} opened"
        shutter.button_text_closed = f"{name} closed"
        shutter._refresh_shutter_widget()
        _shutters.append(shutter)
        qtbot.addWidget(shutter)
    return tuple(_shutters)  # type: ignore


@pytest.mark.xfail(reason="flaky test")
def test_create_shutter_widgets(qtbot: QtBot):
    shutter, state_dev_shutter, multi_shutter = _make_shutters(qtbot)

    assert shutter.shutter_button.text() == "Shutter opened"
    assert not shutter.shutter_button.isEnabled()
    assert state_dev_shutter.shutter_button.text() == "StateDev Shutter opened"
    assert state_dev_shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.text() == "Multi Shutter closed"
    assert multi_shutter.autoshutter_checkbox.isChecked()
    assert multi_shutter.shutter_button.isEnabled()


@pytest.mark.xfail(reason="flaky test")
def test_shutter_widget_propertyChanged(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, _, multi_shutter = _make_shutters(qtbot)

    with wait_signal(qtbot, mmc.events.propertyChanged):
        mmc.setProperty("Shutter", "State", False)

    assert not shutter.shutter_button.isEnabled()
    assert not mmc.getShutterOpen("Shutter")
    assert shutter.shutter_button.text() == "Shutter closed"
    assert mmc.getProperty("Shutter", "State") == "0"
    assert multi_shutter.shutter_button.isEnabled()
    assert not mmc.getShutterOpen("Multi Shutter")
    assert multi_shutter.shutter_button.text() == "Multi Shutter closed"
    assert mmc.getProperty("Multi Shutter", "State") == "0"


def test_shutter_widget_autoShutterSet(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, state_dev_shutter, multi_shutter = _make_shutters(qtbot)

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        mmc.setAutoShutter(False)
    assert shutter.shutter_button.isEnabled()
    assert state_dev_shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.isEnabled()
    mmc.setAutoShutter(True)
    assert not shutter.shutter_button.isEnabled()
    assert state_dev_shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.isEnabled()


def test_shutter_widget_configSet(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, state_dev_shutter, multi_shutter = _make_shutters(qtbot)

    with (
        wait_signal(qtbot, mmc.events.configSet),
        wait_signal(qtbot, mmc.events.propertyChanged),
    ):
        mmc.setConfig("Channel", "DAPI")
        mmc.setShutterOpen("Multi Shutter", True)
    assert multi_shutter.shutter_button.text() == "Multi Shutter opened"
    assert mmc.getProperty("Multi Shutter", "State") == "1"
    assert mmc.getShutterOpen("Multi Shutter")
    assert shutter.shutter_button.text() == "Shutter opened"
    assert mmc.getProperty("Shutter", "State") == "1"
    assert mmc.getShutterOpen("Shutter")
    assert state_dev_shutter.shutter_button.text() == "StateDev Shutter opened"
    assert mmc.getShutterOpen("StateDev Shutter")
    assert mmc.getProperty("StateDev", "Label") == "State-1"


def test_shutter_widget_SequenceAcquisition(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, state_dev_shutter, multi_shutter = _make_shutters(qtbot)

    with wait_signal(qtbot, mmc.events.configSet):
        mmc.setConfig("Channel", "DAPI")

    with wait_signal(qtbot, mmc.events.continuousSequenceAcquisitionStarted):
        mmc.startContinuousSequenceAcquisition()
    assert shutter.shutter_button.text() == "Shutter opened"
    assert not shutter.shutter_button.isEnabled()

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        mmc.setAutoShutter(False)
    assert shutter.shutter_button.isEnabled()
    assert state_dev_shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.isEnabled()
    assert shutter.shutter_button.text() == "Shutter opened"

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        mmc.setAutoShutter(True)
    with wait_signal(qtbot, mmc.events.sequenceAcquisitionStopped):
        mmc.stopSequenceAcquisition()
    assert not shutter.shutter_button.isEnabled()
    assert state_dev_shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.isEnabled()
    assert shutter.shutter_button.text() == "Shutter closed"


def test_shutter_widget_autoshutter(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, state_dev_shutter, multi_shutter = _make_shutters(qtbot)

    assert multi_shutter.autoshutter_checkbox.isChecked()

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        multi_shutter.autoshutter_checkbox.setChecked(False)
    assert shutter.shutter_button.isEnabled()
    assert state_dev_shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.isEnabled()

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        multi_shutter.autoshutter_checkbox.setChecked(True)
    assert not shutter.shutter_button.isEnabled()
    assert state_dev_shutter.shutter_button.isEnabled()
    assert multi_shutter.shutter_button.isEnabled()


@pytest.mark.xfail(reason="flaky test")
def test_shutter_widget_button(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, state_dev_shutter, multi_shutter = _make_shutters(qtbot)

    with wait_signal(qtbot, mmc.events.configSet):
        mmc.setConfig("Channel", "DAPI")

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        multi_shutter.autoshutter_checkbox.setChecked(False)

    with wait_signal(qtbot, mmc.events.propertyChanged):
        shutter.shutter_button.click()
    assert shutter.shutter_button.text() == "Shutter closed"
    assert not mmc.getShutterOpen("Shutter")
    assert mmc.getProperty("Shutter", "State") == "0"

    with wait_signal(qtbot, mmc.events.propertyChanged):
        shutter.shutter_button.click()
    assert shutter.shutter_button.text() == "Shutter opened"
    assert mmc.getShutterOpen("Shutter")
    assert mmc.getProperty("Shutter", "State") == "1"

    with wait_signal(qtbot, mmc.events.propertyChanged):
        state_dev_shutter.shutter_button.click()
    assert state_dev_shutter.shutter_button.text() == "StateDev Shutter opened"
    assert mmc.getShutterOpen("StateDev Shutter")
    assert mmc.getProperty("StateDev", "Label") == "State-1"

    with wait_signal(qtbot, mmc.events.propertyChanged):
        state_dev_shutter.shutter_button.click()
    assert state_dev_shutter.shutter_button.text() == "StateDev Shutter closed"
    assert not mmc.getShutterOpen("StateDev Shutter")
    assert mmc.getProperty("StateDev", "Label") == "State-1"

    with wait_signal(qtbot, mmc.events.propertyChanged):
        multi_shutter.shutter_button.click()
    assert multi_shutter.shutter_button.text() == "Multi Shutter opened"
    assert mmc.getShutterOpen("Multi Shutter")
    assert mmc.getProperty("Multi Shutter", "State") == "1"
    assert shutter.shutter_button.text() == "Shutter opened"
    assert mmc.getShutterOpen("Shutter")
    assert mmc.getProperty("Shutter", "State") == "1"
    assert mmc.getShutterOpen("StateDev Shutter")
    assert mmc.getProperty("StateDev", "Label") == "State-1"


def test_shutter_widget_setters(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, _, _ = _make_shutters(qtbot)

    assert shutter.icon_size == 25
    shutter.icon_size = 30
    assert shutter.icon_size == 30

    assert shutter.icon_color_open == GREEN
    shutter.icon_color_open = GRAY
    assert shutter.icon_color_open == GRAY

    assert shutter.icon_color_closed == GRAY
    shutter.icon_color_closed = GREEN
    assert shutter.icon_color_closed == GREEN

    assert shutter.button_text_open == "Shutter opened"
    shutter.button_text_open = "O"
    assert shutter.button_text_open == "O"

    assert shutter.button_text_closed == "Shutter closed"
    shutter.button_text_closed = "C"
    assert shutter.button_text_closed == "C"

    with wait_signal(qtbot, mmc.events.continuousSequenceAcquisitionStarted):
        mmc.startContinuousSequenceAcquisition()
    assert shutter.shutter_button.text() == "O"
    with wait_signal(qtbot, mmc.events.sequenceAcquisitionStopped):
        mmc.stopSequenceAcquisition()
    assert shutter.shutter_button.text() == "C"


def test_shutter_widget_UserWarning(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    _, _, multi_shutter = _make_shutters(qtbot)

    assert multi_shutter.shutter_button.text() == "Multi Shutter closed"
    with wait_signal(qtbot, mmc.events.systemConfigurationLoaded):
        with pytest.warns(UserWarning):
            mmc.loadSystemConfiguration("MMConfig_demo.cfg")
            assert multi_shutter.shutter_button.text() == "None"


@pytest.mark.xfail(reason="flaky test")
def test_multi_shutter_state_changed(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, shutter1, multi_shutter = _make_shutters(qtbot)

    with (
        wait_signal(qtbot, mmc.events.propertyChanged),
        wait_signal(qtbot, mmc.events.configSet),
    ):
        mmc.setProperty("Core", "Shutter", "Multi Shutter")
        mmc.setConfig("Channel", "DAPI")

    with wait_signal(qtbot, mmc.events.propertyChanged):
        mmc.setProperty("Multi Shutter", "State", "0")

    assert mmc.getProperty("Multi Shutter", "State") == "0"
    assert mmc.getProperty("Shutter", "State") == "0"

    assert multi_shutter.shutter_button.text() == "Multi Shutter closed"
    assert shutter.shutter_button.text() == "Shutter closed"

    with wait_signal(qtbot, mmc.events.propertyChanged):
        mmc.setProperty("Multi Shutter", "State", "1")

    assert mmc.getProperty("Multi Shutter", "State") == "1"
    assert mmc.getProperty("Shutter", "State") == "1"

    assert multi_shutter.shutter_button.text() == "Multi Shutter opened"
    assert shutter.shutter_button.text() == "Shutter opened"


def test_on_shutter_device_changed(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter, shutter1, multi_shutter = _make_shutters(qtbot)

    with (
        wait_signal(qtbot, mmc.events.propertyChanged),
        wait_signal(qtbot, mmc.events.configSet),
    ):
        mmc.setProperty("Core", "Shutter", "Multi Shutter")
        mmc.setConfig("Channel", "DAPI")

    assert mmc.getShutterDevice() == "Multi Shutter"
    assert not multi_shutter.shutter_button.isEnabled()
    assert shutter.shutter_button.isEnabled()
    assert shutter1.shutter_button.isEnabled()

    with (
        wait_signal(qtbot, mmc.events.propertyChanged),
        wait_signal(qtbot, mmc.events.configSet),
    ):
        mmc.setProperty("Core", "Shutter", "Shutter")
        mmc.setConfig("Channel", "DAPI")

    assert mmc.getShutterDevice() == "Shutter"
    assert multi_shutter.shutter_button.isEnabled()
    assert not shutter.shutter_button.isEnabled()
    assert shutter1.shutter_button.isEnabled()
