from __future__ import annotations

from typing import TYPE_CHECKING, cast

import useq

from pymmcore_widgets.mda import MDAWidget
from pymmcore_widgets.mda._core_positions import CoreConnectedPositionTable

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

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

    pos_table = cast(CoreConnectedPositionTable, wdg.stage_positions)
    pos_table.setValue(MDA.stage_positions)
    assert pos_table.table().rowCount() == 2

    p0 = pos_table.value()[0]
    assert p0.x == MDA.stage_positions[0].x
    assert p0.y == MDA.stage_positions[0].y
    assert p0.z == MDA.stage_positions[0].z

    wdg._mmc.setXYPosition(11, 22)
    wdg._mmc.setZPosition(33)
    pos_table._set_xy_from_core(0)
    pos_table._set_z_from_core(0)
    p0 = pos_table.value()[0]
    assert round(p0.x) == 11
    assert round(p0.y) == 22
    assert round(p0.z) == 33

    pos_table.move_to_selection.setChecked(True)
    pos_table.table().selectRow(0)
    pos_table._on_selection_change()
