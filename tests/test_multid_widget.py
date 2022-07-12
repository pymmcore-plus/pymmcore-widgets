from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

from pymmcore_plus import CMMCorePlus
from useq import MDASequence

from pymmcore_widgets._mda_widget._grid_widget import GridWidget
from pymmcore_widgets._mda_widget._mda_widget import MultiDWidget

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
        stage_positions=(
            {"name": "Pos000", "x": 222, "y": 1, "z": 1},
            {"name": "Pos001", "x": 111, "y": 0, "z": 0},
        ),
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

    grid_wdg.scan_size_spinBox_r.setValue(3)
    grid_wdg.scan_size_spinBox_c.setValue(3)
    grid_wdg.ovelap_spinBox.setValue(15)
    assert grid_wdg.info_lbl.text() == "1.306 mm x 1.306 mm"

    global_mmcore.setProperty("Objective", "Label", "Objective-2")
    assert not global_mmcore.getPixelSizeUm()
    grid_wdg._update_info_label()
    assert grid_wdg.info_lbl.text() == "_ mm x _ mm"

    global_mmcore.setProperty("Objective", "Label", "Nikon 10X S Fluor")

    mock = Mock()
    grid_wdg.sendPosList.connect(mock)

    grid_wdg.clear_checkbox.setChecked(False)

    grid_wdg._send_positions_grid()

    mock.assert_has_calls(
        [
            call(
                [
                    (-588.8, 588.8, 0.0),
                    (-153.59999999999997, 588.8, 0.0),
                    (281.6, 588.8, 0.0),
                    (281.6, 153.59999999999997, 0.0),
                    (-153.59999999999997, 153.59999999999997, 0.0),
                    (-588.8, 153.59999999999997, 0.0),
                    (-588.8, -281.6, 0.0),
                    (-153.59999999999997, -281.6, 0.0),
                    (281.6, -281.6, 0.0),
                ],
                False,
            )
        ]
    )
