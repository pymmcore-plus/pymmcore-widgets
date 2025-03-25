from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import DeviceType

from pymmcore_widgets.control._stage_widget import StageWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_stage_widget(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    # test XY stage
    stage_xy = StageWidget("XY", levels=3, absolute_positioning=True)
    stage_xy._poll_cb.setChecked(True)
    stage_xy.show()
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
    assert stage_xy._x_pos.value() == 0
    assert stage_xy._y_pos.value() == 0

    x_pos = global_mmcore.getXPosition()
    y_pos = global_mmcore.getYPosition()
    assert x_pos == -0.0
    assert y_pos == -0.0

    xy_up_3 = stage_xy._move_btns.layout().itemAtPosition(0, 3)
    xy_up_3.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert (
        (y_pos + (stage_xy.step() * 3)) - 1
        < global_mmcore.getYPosition()
        < (y_pos + (stage_xy.step() * 3)) + 1
    )
    assert stage_xy._x_pos.value() == 0
    qtbot.waitUntil(lambda: stage_xy._y_pos.value() == 15)

    xy_left_1 = stage_xy._move_btns.layout().itemAtPosition(3, 2)
    xy_left_1.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert (
        (x_pos - stage_xy.step()) - 1
        < global_mmcore.getXPosition()
        < (x_pos - stage_xy.step()) + 1
    )
    qtbot.waitUntil(lambda: stage_xy._x_pos.value() == -5)
    assert stage_xy._y_pos.value() == 15

    stage_xy._x_pos.setValue(5)
    stage_xy._x_pos.editingFinished.emit()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert 4 < global_mmcore.getXPosition() < 6

    stage_xy._y_pos.setValue(5)
    stage_xy._y_pos.editingFinished.emit()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert 4 < global_mmcore.getYPosition() < 6

    global_mmcore.setXYPosition(0.0, 0.0)
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    qtbot.waitUntil(lambda: stage_xy._x_pos.value() == 0)
    qtbot.waitUntil(lambda: stage_xy._y_pos.value() == 0)

    stage_xy.snap_checkbox.setChecked(True)
    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        global_mmcore.waitForDeviceType(DeviceType.XYStage)
        xy_up_3.widget().click()
    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        stage_xy._x_pos.setValue(10)
        stage_xy._x_pos.editingFinished.emit()
    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        stage_xy._y_pos.setValue(10)
        stage_xy._y_pos.editingFinished.emit()

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
    assert stage_z._y_pos.value() == 0

    z_pos = global_mmcore.getPosition()
    assert z_pos == 0.0

    z_up_2 = stage_z._move_btns.layout().itemAtPosition(1, 3)
    z_up_2.widget().click()
    assert (
        (z_pos + (stage_z.step() * 2)) - 1
        < global_mmcore.getPosition()
        < (z_pos + (stage_z.step() * 2)) + 1
    )
    assert stage_z._y_pos.value() == 30

    global_mmcore.waitForDevice("Z")
    stage_z._y_pos.setValue(5)
    stage_z._y_pos.editingFinished.emit()
    assert 4 < global_mmcore.getPosition() < 6

    global_mmcore.waitForDevice("Z")
    global_mmcore.setPosition(0.0)
    z_pos = global_mmcore.getPosition()
    assert stage_z._y_pos.value() == 0

    stage_z.snap_checkbox.setChecked(True)
    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        global_mmcore.waitForDevice("Z")
        z_up_2.widget().click()
    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        stage_xy._y_pos.setValue(10)
        stage_xy._y_pos.editingFinished.emit()

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


def test_enable_position_buttons(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    # Absolute positioning disabled
    stage_xy = StageWidget("XY", levels=3)
    # Phase 1: position buttons cannot be enabled before the menu action is toggled
    qtbot.addWidget(stage_xy)
    assert not stage_xy._x_pos.isEnabled()
    assert not stage_xy._y_pos.isEnabled()
    stage_xy._enable_wdg(False)
    assert not stage_xy._x_pos.isEnabled()
    assert not stage_xy._y_pos.isEnabled()
    stage_xy._enable_wdg(True)
    assert not stage_xy._x_pos.isEnabled()
    assert not stage_xy._y_pos.isEnabled()
    # Phase 2: Trigger menu action, buttons can now be enabled
    stage_xy._pos_toggle_action.trigger()
    assert stage_xy._x_pos.isEnabled()
    assert stage_xy._y_pos.isEnabled()
    stage_xy._enable_wdg(False)
    assert not stage_xy._x_pos.isEnabled()
    assert not stage_xy._y_pos.isEnabled()
    stage_xy._enable_wdg(True)
    assert stage_xy._x_pos.isEnabled()
    assert stage_xy._y_pos.isEnabled()
    stage_xy._pos_toggle_action.trigger()
    assert not stage_xy._x_pos.isEnabled()
    assert not stage_xy._y_pos.isEnabled()
    # Phase 3: Set absolute positioning using API
    # Should be identical to Phase 2
    stage_xy.enable_absolute_positioning(True)
    assert stage_xy._pos_toggle_action.isChecked()
    assert stage_xy._x_pos.isEnabled()
    assert stage_xy._y_pos.isEnabled()
    stage_xy._enable_wdg(False)
    assert not stage_xy._x_pos.isEnabled()
    assert not stage_xy._y_pos.isEnabled()
    stage_xy._enable_wdg(True)
    assert stage_xy._x_pos.isEnabled()
    assert stage_xy._y_pos.isEnabled()
    stage_xy.enable_absolute_positioning(False)
    assert not stage_xy._pos_toggle_action.isChecked()
    assert not stage_xy._x_pos.isEnabled()
    assert not stage_xy._y_pos.isEnabled()


def test_invert_axis(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    stage_xy = StageWidget("XY", levels=3)
    qtbot.addWidget(stage_xy)

    assert not stage_xy._invert_x.isHidden()
    assert not stage_xy._invert_y.isHidden()

    xy_up_3 = stage_xy._move_btns.layout().itemAtPosition(0, 3)
    xy_left_1 = stage_xy._move_btns.layout().itemAtPosition(3, 2)

    stage_xy.setStep(15.0)

    xy_left_1.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert global_mmcore.getXPosition() == -15.0
    xy_left_1.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert global_mmcore.getXPosition() == -30.0
    global_mmcore.waitForSystem()
    stage_xy._invert_x.setChecked(True)
    xy_left_1.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    xy_left_1.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert global_mmcore.getXPosition() == 0.0

    global_mmcore.waitForSystem()
    xy_up_3.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert global_mmcore.getYPosition() == 45.0
    global_mmcore.waitForSystem()
    stage_xy._invert_y.setChecked(True)
    xy_up_3.widget().click()
    global_mmcore.waitForDeviceType(DeviceType.XYStage)
    assert global_mmcore.getYPosition() == 0.0

    stage_z = StageWidget("Z", levels=3)
    qtbot.addWidget(stage_z)

    assert stage_z._invert_x.isHidden()

    z_up_2 = stage_z._move_btns.layout().itemAtPosition(1, 3)
    z_up_2.widget().click()

    assert global_mmcore.getPosition() == 20.0
