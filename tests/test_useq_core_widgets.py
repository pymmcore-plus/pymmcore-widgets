from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import useq
from qtpy.QtCore import QTimer

from pymmcore_widgets.mda import MDAWidget
from pymmcore_widgets.mda._core_grid import CoreConnectedGridPlanWidget
from pymmcore_widgets.mda._core_positions import CoreConnectedPositionTable
from pymmcore_widgets.mda._core_z import CoreConnectedZPlanWidget
from pymmcore_widgets.useq_widgets._positions import _MDAPopup

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot

TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")

MDA = useq.MDASequence(
    time_plan=useq.TIntervalLoops(interval=0.01, loops=2),
    stage_positions=[(0, 1, 2), useq.Position(x=42, y=0, z=3)],
    channels=[{"config": "DAPI", "exposure": 1}],
    z_plan=useq.ZRangeAround(range=1, step=0.3),
    grid_plan=useq.GridRowsColumns(rows=2, columns=1),
    axis_order="tpgzc",
    keep_shutter_open_across=("z",),
)


def test_core_connected_mda_wdg(qtbot: QtBot):
    wdg = MDAWidget()
    core = wdg._mmc
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)
    new_grid = MDA.grid_plan.replace(fov_width=512, fov_height=512)
    assert wdg.value().replace(metadata={}) == MDA.replace(grid_plan=new_grid)

    with qtbot.waitSignal(wdg._mmc.mda.events.sequenceFinished):
        wdg.control_btns.run_btn.click()

    assert wdg.control_btns.pause_btn.text() == "Pause"
    core.mda.events.sequencePauseToggled.emit(True)
    assert wdg.control_btns.pause_btn.text() == "Resume"
    core.mda.events.sequencePauseToggled.emit(False)
    assert wdg.control_btns.pause_btn.text() == "Pause"
    wdg.control_btns._disconnect()
    wdg._disconnect()


def test_core_connected_position_wdg(qtbot: QtBot, qapp) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)
    pos_table.setValue(MDA.stage_positions)
    assert pos_table.table().rowCount() == 2

    p0 = pos_table.value()[0]
    assert p0.x == MDA.stage_positions[0].x
    assert p0.y == MDA.stage_positions[0].y
    assert p0.z == MDA.stage_positions[0].z

    wdg._mmc.setXYPosition(11, 22)
    wdg._mmc.setZPosition(33)
    xyidx = pos_table.table().indexOf(pos_table._xy_btn_col)
    z_idx = pos_table.table().indexOf(pos_table._z_btn_col)
    # # i'm not sure why click() isn't working... but this is
    pos_table.table().cellWidget(0, xyidx).clicked.emit()
    pos_table.table().cellWidget(0, z_idx).clicked.emit()
    p0 = pos_table.value()[0]
    assert round(p0.x) == 11
    assert round(p0.y) == 22
    assert round(p0.z) == 33

    wdg._mmc.waitForSystem()
    pos_table.move_to_selection.setChecked(True)
    pos_table.table().selectRow(0)
    pos_table._on_selection_change()


def _assert_position_wdg_state(
    stage: str, pos_table: CoreConnectedPositionTable, is_hidden: bool
) -> None:
    """Assert the correct widget state for the given stage."""
    if stage == "XY":
        # both x and y columns should be hidden if XY device is not loaded/selected
        x_col = pos_table.table().indexOf(pos_table.X)
        y_col = pos_table.table().indexOf(pos_table.Y)
        x_hidden = pos_table.table().isColumnHidden(x_col)
        y_hidden = pos_table.table().isColumnHidden(y_col)
        assert x_hidden == is_hidden
        assert y_hidden == is_hidden
        # the set position button should be hidden if XY device is not loaded/selected
        xy_btn_col = pos_table.table().indexOf(pos_table._xy_btn_col)
        xy_btn_hidden = pos_table.table().isColumnHidden(xy_btn_col)
        assert xy_btn_hidden == is_hidden
        # values() should return None for x and y if XY device is not loaded/selected
        if is_hidden:
            xy = [(v.x, v.y) for v in pos_table.value()]
            assert all(x is None and y is None for x, y in xy)
    elif stage == "Z":
        # the set position button should be hidden
        z_btn_col = pos_table.table().indexOf(pos_table._z_btn_col)
        assert pos_table.table().isColumnHidden(z_btn_col)
        # values() should return None for z
        if is_hidden:
            z = [v.z for v in pos_table.value()]
            assert all(z is None for z in z)
        # the include z checkbox should be unchecked
        assert not pos_table.include_z.isChecked()
        # the include z checkbox should be disabled if Z device is not loaded/selected
        assert pos_table.include_z.isEnabled() == (not is_hidden)
        # tooltip should should change if Z device is not loaded/selected
        tooltip = "Focus device unavailable." if is_hidden else ""
        assert pos_table.include_z.toolTip() == tooltip


@pytest.mark.parametrize("stage", ["XY", "Z"])
def test_core_connected_position_wdg_cfg_loaded(
    stage: str, qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    # stage device is not loaded, the respective columns should be hidden and
    # values() should return None. This behavior should change
    # when a new cfg stage device is loaded.
    mmc = global_mmcore
    mmc.unloadDevice(stage)

    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg.setValue(MDA)

    # stage is not loaded
    _assert_position_wdg_state(stage, pos_table, is_hidden=True)

    with qtbot.waitSignal(mmc.events.systemConfigurationLoaded):
        mmc.loadSystemConfiguration(TEST_CONFIG)

    # stage is loaded (systemConfigurationLoaded is triggered)
    _assert_position_wdg_state(stage, pos_table, is_hidden=False)


@pytest.mark.parametrize("stage", ["XY", "Z"])
def test_core_connected_position_wdg_property_changed(
    stage: str, qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    # if stage device are loaded but not set as default device, their respective columns
    # should be hidden and values() should return None. This behavior should change when
    # stage device is set as default device.
    mmc = global_mmcore

    with qtbot.waitSignal(mmc.events.propertyChanged):
        if stage == "XY":
            mmc.setProperty("Core", "XYStage", "")
        elif stage == "Z":
            mmc.setProperty("Core", "Focus", "")

    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg.setValue(MDA)

    # stage is not set as default device
    _assert_position_wdg_state(stage, pos_table, is_hidden=True)

    with qtbot.waitSignal(mmc.events.propertyChanged):
        if stage == "XY":
            mmc.setProperty("Core", "XYStage", "XY")
        elif stage == "Z":
            mmc.setProperty("Core", "Focus", "Z")

    # stage is set as default device (propertyChanged is triggered)
    _assert_position_wdg_state(stage, pos_table, is_hidden=False)


def test_core_position_table_add_position(qtbot: QtBot) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg._mmc.setXYPosition(11, 22)
    wdg._mmc.setZPosition(33)
    with qtbot.waitSignals([pos_table.valueChanged], order="strict", timeout=1000):
        pos_table.act_add_row.trigger()
    val = pos_table.value()[-1]
    assert round(val.x, 1) == 11
    assert round(val.y, 1) == 22
    assert round(val.z, 1) == 33


def test_core_connected_relative_z_plan(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg._mmc.setXYPosition(11, 22)
    wdg._mmc.setZPosition(33)
    wdg._mmc.waitForSystem()

    MDA = useq.MDASequence(
        channels=[{"config": "DAPI", "exposure": 1}],
        z_plan=useq.ZRangeAround(range=1, step=0.3),
        axis_order="pzc",
    )
    wdg.setValue(MDA)

    val = wdg.value().stage_positions[-1]
    assert round(val.x, 1) == 11
    assert round(val.y, 1) == 22
    assert round(val.z, 1) == 33


def test_position_table_connected_popup(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)
    seq_col = pos_table.table().indexOf(pos_table.SEQ)
    btn = pos_table.table().cellWidget(0, seq_col)

    def handle_dialog():
        popup = btn.findChild(_MDAPopup)
        mda = popup.mda_tabs
        assert isinstance(mda.z_plan, CoreConnectedZPlanWidget)
        assert isinstance(mda.grid_plan, CoreConnectedGridPlanWidget)
        popup.accept()

    QTimer.singleShot(100, handle_dialog)

    with qtbot.waitSignal(wdg.valueChanged):
        btn.seq_btn.click()
