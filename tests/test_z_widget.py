from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._mda import ZStackWidget
from pymmcore_widgets._mda._zstack_widget import ZTopBottomSelect, _BasicWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_z_stack_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    z = ZStackWidget()
    qtbot.addWidget(z)

    mmc = global_mmcore

    assert mmc.getFocusDevice() == "Z"
    assert z._z_device_combo.value() == "Z"

    assert z._zmode_tabs.isEnabled()
    z._zmode_tabs.setCurrentIndex(0)
    wdg = cast("ZTopBottomSelect", z._zmode_tabs.currentWidget())
    assert wdg.z_device == "Z"

    mmc.setPosition("Z", 30)
    mmc.waitForSystem()
    wdg._top_btn.click()
    assert wdg._top_spinbox.value() == 30
    mmc.setPosition("Z", 10)
    mmc.waitForSystem()
    wdg._bottom_btn.click()

    assert wdg._bottom_spinbox.value() == 10
    assert wdg.z_range() == 20
    assert z._zstep_spinbox.value() == 1
    assert z.n_images() == 21
    assert z.value() == {"top": 30.0, "bottom": 10.0, "z_device": "Z", "step": 1.0}

    z._zmode_tabs.setCurrentIndex(1)
    assert z.value() == {"range": 5.0, "z_device": "Z", "step": 1.0}

    z._zmode_tabs.setCurrentIndex(2)
    assert z.value() == {"above": 2.5, "below": 2.5, "z_device": "Z", "step": 1.0}

    z._z_device_combo.setValue("None")
    assert z.value() == {"go_up": True, "z_device": None}


def test_z_stack_widget_state(qtbot: QtBot):
    z = ZStackWidget()
    qtbot.addWidget(z)

    wdg = cast("_BasicWidget", z._zmode_tabs.currentWidget())
    zplan = {"range": 4, "step": 0.5, "z_device": "Z"}
    z.set_state(zplan)
    assert z.value() == zplan
    assert wdg.z_device == "Z"

    zplan1 = {"range": 4, "step": 0.5}
    z.set_state(zplan1)
    assert z.value() == zplan
    assert wdg.z_device == "Z"

    wdg = cast("_BasicWidget", z._zmode_tabs.currentWidget())
    zplan = {"range": 4, "step": 0.5, "z_device": "None"}
    z.set_state(zplan)
    assert wdg.z_device == ""
    assert z.value() == {"go_up": True, "z_device": None}
