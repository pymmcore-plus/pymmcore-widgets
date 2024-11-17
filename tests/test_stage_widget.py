from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets.control._stage_widget import StageWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_stage_widget(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    # test XY stage
    stage_xy = StageWidget("XY", levels=3)
    qtbot.addWidget(stage_xy)

    assert global_mmcore.getXYStageDevice() == "XY"
    assert stage_xy._set_as_default_btn.isChecked()
    global_mmcore.setProperty("Core", "XYStage", "")
    assert not global_mmcore.getXYStageDevice()
    assert not stage_xy._set_as_default_btn.isChecked()
    stage_xy._set_as_default_btn.setChecked(True)
    assert global_mmcore.getXYStageDevice() == "XY"
    assert stage_xy._set_as_default_btn.isChecked()

    stage_xy.setStep(5.0)
    assert stage_xy.step() == 5.0
    assert stage_xy._pos_label.text() == "X: -0.0  Y: -0.0"

    x_pos = global_mmcore.getXPosition()
    y_pos = global_mmcore.getYPosition()
    assert x_pos == -0.0
    assert y_pos == -0.0

    xy_up_3 = stage_xy._move_btns.layout().itemAtPosition(0, 3)
    xy_up_3.widget().click()
    assert (
        (y_pos + (stage_xy.step() * 3)) - 1
        < global_mmcore.getYPosition()
        < (y_pos + (stage_xy.step() * 3)) + 1
    )
    assert stage_xy._pos_label.text() == "X: -0.0  Y: 15.0"

    xy_left_1 = stage_xy._move_btns.layout().itemAtPosition(3, 2)
    global_mmcore.waitForDevice("XY")
    xy_left_1.widget().click()
    assert (
        (x_pos - stage_xy.step()) - 1
        < global_mmcore.getXPosition()
        < (x_pos - stage_xy.step()) + 1
    )
    assert stage_xy._pos_label.text() == "X: -5.0  Y: 15.0"

    global_mmcore.waitForDevice("XY")
    global_mmcore.setXYPosition(0.0, 0.0)
    y_pos = global_mmcore.getYPosition()
    x_pos = global_mmcore.getXPosition()
    assert stage_xy._pos_label.text() == "X: -0.0  Y: -0.0"

    stage_xy.snap_checkbox.setChecked(True)
    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        global_mmcore.waitForDevice("XY")
        xy_up_3.widget().click()

    # test Z stage
    stage_z = StageWidget("Z", levels=3)
    stage_z1 = StageWidget("Z1", levels=3)

    qtbot.addWidget(stage_z)
    qtbot.addWidget(stage_z1)

    assert global_mmcore.getFocusDevice() == "Z"
    assert stage_z._set_as_default_btn.isChecked()
    assert not stage_z1._set_as_default_btn.isChecked()
    global_mmcore.setProperty("Core", "Focus", "Z1")
    assert global_mmcore.getFocusDevice() == "Z1"
    assert not stage_z._set_as_default_btn.isChecked()
    assert stage_z1._set_as_default_btn.isChecked()
    stage_z._set_as_default_btn.setChecked(True)
    assert global_mmcore.getFocusDevice() == "Z"
    assert stage_z._set_as_default_btn.isChecked()
    assert not stage_z1._set_as_default_btn.isChecked()

    stage_z.setStep(15.0)
    assert stage_z.step() == 15.0
    assert stage_z._pos_label.text() == "Z: 0.0"

    z_pos = global_mmcore.getPosition()
    assert z_pos == 0.0

    z_up_2 = stage_z._move_btns.layout().itemAtPosition(1, 3)
    z_up_2.widget().click()
    assert (
        (z_pos + (stage_z.step() * 2)) - 1
        < global_mmcore.getPosition()
        < (z_pos + (stage_z.step() * 2)) + 1
    )
    assert stage_z._pos_label.text() == "Z: 30.0"

    global_mmcore.waitForDevice("Z")
    global_mmcore.setPosition(0.0)
    z_pos = global_mmcore.getPosition()
    assert stage_z._pos_label.text() == "Z: 0.0"

    stage_z.snap_checkbox.setChecked(True)
    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        global_mmcore.waitForDevice("Z")
        z_up_2.widget().click()

    # disconnect
    assert global_mmcore.getFocusDevice() == "Z"
    assert stage_z._set_as_default_btn.isChecked()
    assert not stage_z1._set_as_default_btn.isChecked()
    stage_z._disconnect()
    stage_z1._disconnect()
    # once disconnected, core changes shouldn't call out to the widget
    global_mmcore.setProperty("Core", "Focus", "Z1")
    assert stage_z._set_as_default_btn.isChecked()
    assert not stage_z1._set_as_default_btn.isChecked()


def test_invert_axis(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    stage_xy = StageWidget("XY", levels=3)
    qtbot.addWidget(stage_xy)

    assert not stage_xy._invert_x.isHidden()
    assert not stage_xy._invert_y.isHidden()

    xy_up_3 = stage_xy._move_btns.layout().itemAtPosition(0, 3)
    xy_left_1 = stage_xy._move_btns.layout().itemAtPosition(3, 2)

    stage_xy.setStep(15.0)

    xy_left_1.widget().click()
    assert global_mmcore.getXPosition() == -15.0
    global_mmcore.waitForSystem()
    stage_xy._invert_x.setChecked(True)
    xy_left_1.widget().click()
    assert global_mmcore.getXPosition() == 0.0

    global_mmcore.waitForSystem()
    xy_up_3.widget().click()
    assert global_mmcore.getYPosition() == 45.0
    global_mmcore.waitForSystem()
    stage_xy._invert_y.setChecked(True)
    xy_up_3.widget().click()
    assert global_mmcore.getYPosition() == 0.0

    stage_z = StageWidget("Z", levels=3)
    qtbot.addWidget(stage_z)

    assert stage_z._invert_x.isHidden()

    z_up_2 = stage_z._move_btns.layout().itemAtPosition(1, 3)
    z_up_2.widget().click()

    assert global_mmcore.getPosition() == 20.0
