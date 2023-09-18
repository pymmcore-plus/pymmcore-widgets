from __future__ import annotations

from typing import TYPE_CHECKING

import useq

from pymmcore_widgets.mda import MDAWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

MDA = useq.MDASequence(
    time_plan=useq.TIntervalLoops(interval=4, loops=3),
    stage_positions=[(0, 1, 2), useq.Position(x=42, y=0, z=3)],
    channels=[{"config": "DAPI", "exposure": 42}],
    z_plan=useq.ZRangeAround(range=10, step=0.3),
    grid_plan=useq.GridRowsColumns(rows=10, columns=3),
    axis_order="tpgzc",
    keep_shutter_open_across=("z",),
)


def test_core_connected_mda_wdg(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)
    new_grid = MDA.grid_plan.replace(fov_width=512, fov_height=512)
    assert wdg.value().replace(metadata={}) == MDA.replace(grid_plan=new_grid)
