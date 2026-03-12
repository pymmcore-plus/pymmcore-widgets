from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pymmcore_widgets.control._shutter_widget import ShuttersWidget
from tests._utils import wait_signal

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def _make_shutter(
    qtbot: QtBot,
    mmcore: CMMCorePlus,
    device: str = "Shutter",
    autoshutter: bool = True,
) -> ShuttersWidget:
    wdg = ShuttersWidget(
        device,
        autoshutter=autoshutter,
        button_text_open=f"{device} opened",
        button_text_closed=f"{device} closed",
        mmcore=mmcore,
    )
    qtbot.addWidget(wdg)
    return wdg


def test_initial_state(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore

    # Core shutter ("Shutter") with autoshutter on → button disabled
    shutter = _make_shutter(qtbot, mmc, "Shutter", autoshutter=False)
    assert not shutter.shutter_button.isEnabled()

    # Non-core shutter → button enabled
    state_dev = _make_shutter(qtbot, mmc, "StateDev Shutter", autoshutter=False)
    assert state_dev.shutter_button.isEnabled()

    # Autoshutter checkbox shown and checked
    multi = _make_shutter(qtbot, mmc, "Multi Shutter", autoshutter=True)
    assert multi.autoshutter_checkbox.isChecked()
    assert multi.shutter_button.isEnabled()


def test_shutter_state_change(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter = _make_shutter(qtbot, mmc, "Shutter")

    # Explicitly set to closed, then open
    # shutterOpenChanged fires asynchronously from C++ callbacks
    mmc.setShutterOpen("Shutter", False)
    qtbot.waitUntil(lambda: not shutter._is_open, timeout=2000)
    assert shutter.shutter_button.text() == "Shutter closed"

    mmc.setShutterOpen("Shutter", True)
    qtbot.waitUntil(lambda: shutter._is_open, timeout=2000)
    assert shutter.shutter_button.text() == "Shutter opened"


def test_autoshutter_enables_disables(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter = _make_shutter(qtbot, mmc, "Shutter")
    state_dev = _make_shutter(qtbot, mmc, "StateDev Shutter")

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        mmc.setAutoShutter(False)
    assert shutter.shutter_button.isEnabled()
    assert state_dev.shutter_button.isEnabled()

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        mmc.setAutoShutter(True)
    assert not shutter.shutter_button.isEnabled()
    assert state_dev.shutter_button.isEnabled()


def test_config_set_updates_enabled(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter = _make_shutter(qtbot, mmc, "Shutter")

    with wait_signal(qtbot, mmc.events.configSet):
        mmc.setConfig("Channel", "DAPI")
    # Core shutter + autoshutter on → disabled
    assert not shutter.shutter_button.isEnabled()


def test_autoshutter_checkbox(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter = _make_shutter(qtbot, mmc, "Shutter", autoshutter=True)
    assert shutter.autoshutter_checkbox.isChecked()

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        shutter.autoshutter_checkbox.setChecked(False)
    assert shutter.shutter_button.isEnabled()

    with wait_signal(qtbot, mmc.events.autoShutterSet):
        shutter.autoshutter_checkbox.setChecked(True)
    assert not shutter.shutter_button.isEnabled()


def test_button_click_toggles(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    mmc.setAutoShutter(False)

    shutter = _make_shutter(qtbot, mmc, "Shutter")

    # Set a known state first — wait for async callback delivery
    with wait_signal(qtbot, mmc.events.shutterOpenChanged):
        mmc.setShutterOpen("Shutter", True)

    shutter.shutter_button.click()
    qtbot.waitUntil(lambda: not shutter._is_open, timeout=2000)
    assert shutter.shutter_button.text() == "Shutter closed"
    assert not mmc.getShutterOpen("Shutter")

    shutter.shutter_button.click()
    qtbot.waitUntil(lambda: shutter._is_open, timeout=2000)
    assert shutter.shutter_button.text() == "Shutter opened"
    assert mmc.getShutterOpen("Shutter")


def test_system_config_loaded(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    multi = _make_shutter(qtbot, mmc, "Multi Shutter")

    with pytest.warns(UserWarning):
        with wait_signal(qtbot, mmc.events.systemConfigurationLoaded):
            mmc.loadSystemConfiguration("MMConfig_demo.cfg")
    assert multi.shutter_button.text() == "None"


def test_core_shutter_device_change(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore
    shutter = _make_shutter(qtbot, mmc, "Shutter")
    multi = _make_shutter(qtbot, mmc, "Multi Shutter")

    # Initially Shutter is core shutter → disabled, Multi is not → enabled
    assert not shutter.shutter_button.isEnabled()
    assert multi.shutter_button.isEnabled()

    # Change core shutter to Multi Shutter
    with wait_signal(qtbot, mmc.events.propertyChanged):
        mmc.setProperty("Core", "Shutter", "Multi Shutter")
    assert shutter.shutter_button.isEnabled()
    assert not multi.shutter_button.isEnabled()

    # Change back
    with wait_signal(qtbot, mmc.events.propertyChanged):
        mmc.setProperty("Core", "Shutter", "Shutter")
    assert not shutter.shutter_button.isEnabled()
    assert multi.shutter_button.isEnabled()


def test_multi_shutter_propagates(qtbot: QtBot, global_mmcore: CMMCorePlus):
    """When Multi Shutter opens, individual sub-shutter widgets should update."""
    mmc = global_mmcore
    mmc.setAutoShutter(False)

    # Configure Multi Shutter to include Shutter as a sub-shutter
    mmc.setProperty("Multi Shutter", "Physical Shutter 1", "Shutter")

    # Create widgets for a physical shutter and the Multi Shutter
    phys = _make_shutter(qtbot, mmc, "Shutter")
    multi = _make_shutter(qtbot, mmc, "Multi Shutter")

    # Ensure both start closed
    mmc.setShutterOpen("Shutter", False)
    mmc.setShutterOpen("Multi Shutter", False)

    # Open Multi Shutter — C++ emits shutterOpenChanged for each sub-shutter
    mmc.setShutterOpen("Multi Shutter", True)
    qtbot.waitUntil(lambda: phys._is_open and multi._is_open, timeout=2000)
    assert multi.shutter_button.text() == "Multi Shutter opened"
    assert phys.shutter_button.text() == "Shutter opened"

    # Close Multi Shutter — sub-shutter widget should update too
    mmc.setShutterOpen("Multi Shutter", False)
    qtbot.waitUntil(lambda: not phys._is_open and not multi._is_open, timeout=2000)
    assert multi.shutter_button.text() == "Multi Shutter closed"
    assert phys.shutter_button.text() == "Shutter closed"
