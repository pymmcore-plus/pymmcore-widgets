from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import useq

from pymmcore_widgets.mda import MDAWidget
from pymmcore_widgets.mda._core_positions import CoreConnectedPositionTable

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


def _assert(stage: str, pos_table: CoreConnectedPositionTable) -> None:
    if stage == "Autofocus":
        af_col = pos_table.table().indexOf(pos_table.AF)
        af_btn_col = pos_table.table().indexOf(pos_table._af_btn_col)
        assert not pos_table.use_af.isChecked()
        assert not pos_table.use_af.isEnabled()
        assert pos_table.use_af.toolTip() == "No Autofocus device selected."
        assert pos_table.table().isColumnHidden(af_col)
        assert pos_table.table().isColumnHidden(af_btn_col)
    elif stage == "XY":
        x_col = pos_table.table().indexOf(pos_table.X)
        y_col = pos_table.table().indexOf(pos_table.Y)
        xy_btn_col = pos_table.table().indexOf(pos_table._xy_btn_col)
        assert pos_table.table().isColumnHidden(x_col)
        assert pos_table.table().isColumnHidden(y_col)
        assert pos_table.table().isColumnHidden(xy_btn_col)
        xy = [(v.x, v.y) for v in pos_table.value()]
        assert all(x is None and y is None for x, y in xy)
    elif stage == "Z":
        z_col = pos_table.table().indexOf(pos_table.Z)
        z_btn_col = pos_table.table().indexOf(pos_table._z_btn_col)
        assert not pos_table.include_z.isChecked()
        assert not pos_table.include_z.isEnabled()
        assert pos_table.include_z.toolTip() == "No Focus device selected."
        assert pos_table.table().isColumnHidden(z_col)
        assert pos_table.table().isColumnHidden(z_btn_col)
        z = [v.z for v in pos_table.value()]
        assert all(z is None for z in z)


@pytest.mark.parametrize("stage", ["XY", "Z", "Autofocus"])
def test_core_connected_position_wdg_cfg_loaded(
    stage: str, qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    # if XY or Z device is not loaded, the XY or Z columns should be hidden and
    # values() should return None for x, y and/or z. This behavior should change
    # when a new cfg with XY or Z device is loaded.
    mmc = global_mmcore
    mmc.unloadDevice(stage)

    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg.setValue(MDA)
    _assert(stage, pos_table)

    with qtbot.waitSignal(mmc.events.systemConfigurationLoaded):
        mmc.loadSystemConfiguration(TEST_CONFIG)

    if stage == "XY":
        assert not pos_table.table().isColumnHidden(
            pos_table.table().indexOf(pos_table.X)
        )
        assert not pos_table.table().isColumnHidden(
            pos_table.table().indexOf(pos_table.Y)
        )
    elif stage == "Z":
        assert pos_table.include_z.isEnabled()
        assert pos_table.include_z.toolTip() == ""

    elif stage == "Autofocus":
        assert pos_table.use_af.isEnabled()
        assert pos_table.use_af.toolTip() == ""


@pytest.mark.parametrize("stage", ["XY", "Z", "Autofocus"])
def test_core_connected_position_wdg_property_changed(
    stage: str, qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    # if XY or Z device is are loaded but not set as default device, the XY or Z columns
    # should be hidden and values() should return None for x, y and/or z. This behavior
    # should change when XY or Z device is set as default device.
    mmc = global_mmcore

    with qtbot.waitSignal(mmc.events.propertyChanged):
        if stage == "XY":
            mmc.setProperty("Core", "XYStage", "")
        elif stage == "Z":
            mmc.setProperty("Core", "Focus", "")
        elif stage == "Autofocus":
            mmc.setProperty("Core", "AutoFocus", "")
        mmc.waitForSystem()

    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg.setValue(MDA)
    _assert(stage, pos_table)

    with qtbot.waitSignal(mmc.events.propertyChanged):
        if stage == "XY":
            mmc.setProperty("Core", "XYStage", "XY")
            assert not pos_table.table().isColumnHidden(
                pos_table.table().indexOf(pos_table.X)
            )
            assert not pos_table.table().isColumnHidden(
                pos_table.table().indexOf(pos_table.Y)
            )
        elif stage == "Z":
            mmc.setProperty("Core", "Focus", "Z")
            assert pos_table.include_z.isEnabled()
            assert pos_table.include_z.toolTip() == ""
        elif stage == "Autofocus":
            mmc.setProperty("Core", "AutoFocus", "Autofocus")
            assert pos_table.use_af.isEnabled()
            assert pos_table.use_af.toolTip() == ""
