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

    wdg._set_enabled(False)
    assert not wdg.save_groupBox.isEnabled()
    assert not wdg.time_groupBox.isEnabled()
    assert not wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupBox.isEnabled()
    assert not wdg.stage_pos_groupBox.isEnabled()
    assert not wdg.stack_groupBox.isEnabled()
    wdg._set_enabled(True)

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

    # test add grid positions
    wdg.stage_pos_groupBox.setChecked(True)
    wdg._clear_positions()
    assert wdg.stage_tableWidget.rowCount() == 0
    wdg.grid_Button.click()
    wdg._grid_wdg.scan_size_spinBox_r.setValue(2)
    wdg._grid_wdg.scan_size_spinBox_c.setValue(2)
    wdg._grid_wdg.generate_position_btn.click()
    assert wdg.stage_tableWidget.rowCount() == 4


def test_mda_buttons(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MultiDWidget()
    qtbot.addWidget(wdg)

    assert wdg.channel_tableWidget.rowCount() == 0
    wdg.add_ch_Button.click()
    wdg.add_ch_Button.click()
    assert wdg.channel_tableWidget.rowCount() == 2
    wdg.channel_tableWidget.selectRow(0)
    wdg.remove_ch_Button.click()
    assert wdg.channel_tableWidget.rowCount() == 1
    wdg.clear_ch_Button.click()
    assert wdg.channel_tableWidget.rowCount() == 0

    assert wdg.stage_tableWidget.rowCount() == 0
    wdg.stage_pos_groupBox.setChecked(True)
    wdg.add_pos_Button.click()
    wdg.add_pos_Button.click()
    assert wdg.stage_tableWidget.rowCount() == 2
    wdg.stage_tableWidget.selectRow(0)
    wdg.remove_pos_Button.click()
    assert wdg.stage_tableWidget.rowCount() == 1
    wdg.clear_pos_Button.click()
    assert wdg.stage_tableWidget.rowCount() == 0


def test_mda_grid(qtbot: QtBot, global_mmcore: CMMCorePlus):

    grid_wdg = GridWidget()
    qtbot.addWidget(grid_wdg)

    global_mmcore.setProperty("Objective", "Label", "Objective-2")
    assert not global_mmcore.getPixelSizeUm()
    grid_wdg._update_info_label()
    assert grid_wdg.info_lbl.text() == "_ mm x _ mm"

    global_mmcore.setProperty("Objective", "Label", "Nikon 10X S Fluor")

    # w/o overlap
    grid_wdg.scan_size_spinBox_r.setValue(2)
    grid_wdg.scan_size_spinBox_c.setValue(2)
    grid_wdg.ovelap_spinBox.setValue(0)
    assert grid_wdg.info_lbl.text() == "1.024 mm x 1.024 mm"

    mock = Mock()
    grid_wdg.sendPosList.connect(mock)

    grid_wdg.clear_checkbox.setChecked(True)

    grid_wdg._send_positions_grid()

    mock.assert_has_calls(
        [
            call(
                [
                    (-256.0, 256.0, 0.0),
                    (256.0, 256.0, 0.0),
                    (256.0, -256.0, 0.0),
                    (-256.0, -256.0, 0.0),
                ],
                True,
            )
        ]
    )

    # with overlap
    grid_wdg.scan_size_spinBox_r.setValue(3)
    grid_wdg.scan_size_spinBox_c.setValue(3)
    grid_wdg.ovelap_spinBox.setValue(15)
    assert grid_wdg.info_lbl.text() == "1.306 mm x 1.306 mm"

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
