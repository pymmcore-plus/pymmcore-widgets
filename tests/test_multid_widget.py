from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

from pymmcore_plus import CMMCorePlus
from useq import MDASequence

from pymmcore_widgets.mda_widget._grid_widget import GridWidget
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


def test_mda_grid(qtbot: QtBot, global_mmcore: CMMCorePlus):

    grid_wdg = GridWidget()
    qtbot.addWidget(grid_wdg)

    grid_wdg.scan_size_spinBox_r.setValue(2)
    grid_wdg.scan_size_spinBox_c.setValue(2)
    grid_wdg.ovelap_spinBox.setValue(50)
    assert grid_wdg.info_lbl.text() == "0.512 mm x 0.512 mm"

    mock = Mock()
    grid_wdg.sendPosList.connect(mock)

    grid_wdg.clear_checkbox.setChecked(False)

    grid_wdg._send_positions_grid()

    mock.assert_has_calls(
        [
            call(
                [
                    (-512.0, 512.0, 0.0),
                    (-256.0, 512.0, 0.0),
                    (-256.0, 256.0, 0.0),
                    (-512.0, 256.0, 0.0),
                ],
                False,
            )
        ]
    )
