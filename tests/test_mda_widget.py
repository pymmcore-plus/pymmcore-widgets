from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

from pymmcore_plus import CMMCorePlus
from useq import MDASequence

from pymmcore_widgets._mda_widget._grid_widget import GridWidget
from pymmcore_widgets._mda_widget._mda_widget import MDAWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_mda_widget_load_state(qtbot: QtBot):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 0
    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 0
    assert not wdg.time_groupbox.isChecked()

    wdg._set_enabled(False)
    assert not wdg.time_groupbox.isEnabled()
    assert not wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupbox.isEnabled()
    assert not wdg.stage_pos_groupbox.isEnabled()
    assert not wdg.stack_groupbox.isEnabled()
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
    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 2
    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 2
    assert wdg.time_groupbox.isChecked()

    # round trip
    assert wdg.get_state() == sequence

    # test add grid positions
    wdg.stage_pos_groupbox.setChecked(True)
    wdg._clear_positions()
    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 0
    wdg.stage_pos_groupbox.grid_button.click()
    qtbot.addWidget(wdg._grid_wdg)
    wdg._grid_wdg.scan_size_spinBox_r.setValue(2)
    wdg._grid_wdg.scan_size_spinBox_c.setValue(2)
    wdg._grid_wdg.generate_position_btn.click()
    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 4


def test_mda_buttons(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 0
    wdg.channel_groupbox.add_ch_button.click()
    wdg.channel_groupbox.add_ch_button.click()
    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 2
    wdg.channel_groupbox.channel_tableWidget.selectRow(0)
    wdg.channel_groupbox.remove_ch_button.click()
    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 1
    wdg.channel_groupbox.clear_ch_button.click()
    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 0

    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 0
    wdg.stage_pos_groupbox.setChecked(True)
    wdg.stage_pos_groupbox.add_pos_button.click()
    wdg.stage_pos_groupbox.add_pos_button.click()
    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 2
    wdg.stage_pos_groupbox.stage_tableWidget.selectRow(0)
    wdg.stage_pos_groupbox.remove_pos_button.click()
    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 1
    wdg.stage_pos_groupbox.clear_pos_button.click()
    assert wdg.stage_pos_groupbox.stage_tableWidget.rowCount() == 0


def test_mda_methods(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    wdg._on_mda_started()
    assert not wdg.time_groupbox.isEnabled()
    assert not wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupbox.isEnabled()
    assert not wdg.stage_pos_groupbox.isEnabled()
    assert not wdg.stack_groupbox.isEnabled()
    assert wdg.buttons_wdg.run_button.isHidden()
    assert not wdg.buttons_wdg.pause_button.isHidden()
    assert not wdg.buttons_wdg.cancel_button.isHidden()

    wdg._on_mda_finished()
    assert wdg.time_groupbox.isEnabled()
    assert wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert wdg.channel_groupbox.isEnabled()
    assert wdg.stage_pos_groupbox.isEnabled()
    assert wdg.stack_groupbox.isEnabled()
    assert not wdg.buttons_wdg.run_button.isHidden()
    assert wdg.buttons_wdg.pause_button.isHidden()
    assert wdg.buttons_wdg.cancel_button.isHidden()


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


def test_gui_labels(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 0
    wdg.channel_groupbox.add_ch_button.click()
    assert wdg.channel_groupbox.channel_tableWidget.rowCount() == 1
    assert wdg.channel_groupbox.channel_tableWidget.cellWidget(0, 1).value() == 100.0
    assert not wdg.time_groupbox.isChecked()

    txt = "Minimum total acquisition time: 100.0000 ms.\n"
    assert wdg.time_lbl._total_time_lbl.text() == txt

    assert not wdg.time_groupbox.isChecked()
    wdg.time_groupbox.setChecked(True)
    wdg.time_groupbox.time_comboBox.setCurrentText("ms")

    txt = (
        "Minimum total acquisition time: 100.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt

    wdg.time_groupbox.timepoints_spinBox.setValue(3)
    txt = (
        "Minimum total acquisition time: 300.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt

    wdg.time_groupbox.interval_spinBox.setValue(10)
    txt1 = (
        "Minimum total acquisition time: 300.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    txt2 = "Interval shorter than acquisition time per timepoint."
    assert wdg.time_lbl._total_time_lbl.text() == txt1
    assert wdg.time_groupbox._time_lbl.text() == txt2

    wdg.time_groupbox.interval_spinBox.setValue(200)
    txt1 = (
        "Minimum total acquisition time: 500.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt1
