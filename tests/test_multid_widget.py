from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from useq import MDASequence

from pymmcore_widgets.mda_widget.mda_widget import MultiDWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_multid_load_state(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MultiDWidget()
    qtbot.addWidget(wdg)
    assert wdg.stage_tableWidget.rowCount() == 0
    assert wdg.channel_tableWidget.rowCount() == 0
    assert not wdg.time_groupBox.isChecked()
    sequence = MDASequence(
        channels=[
            {"config": "Cy5", "exposure": 20},
            {"config": "FITC", "exposure": 50},
        ],
        time_plan={"interval": 2, "loops": 5},
        z_plan={"range": 4, "step": 0.5},
        axis_order="tpcz",
        stage_positions=[(222, 1, 1), (111, 0, 0)],
    )
    wdg.set_state(sequence)
    assert wdg.stage_tableWidget.rowCount() == 2
    assert wdg.channel_tableWidget.rowCount() == 2
    assert wdg.time_groupBox.isChecked()

    # round trip
    assert wdg._get_state() == sequence
