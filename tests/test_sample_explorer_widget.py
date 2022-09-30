from __future__ import annotations

from typing import TYPE_CHECKING

from useq import MDASequence

from pymmcore_widgets import SampleExplorer

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_explorer_state(qtbot: QtBot, global_mmcore: CMMCorePlus):
    # sourcery skip: remove-duplicate-set-key

    s_exp = SampleExplorer()
    qtbot.add_widget(s_exp)
    mmc = global_mmcore

    assert len(s_exp._mmc.getLoadedDevices()) > 2
    assert mmc.getChannelGroup() == "Channel"

    s_exp.scan_size_spinBox_c.setValue(2)
    s_exp.scan_size_spinBox_r.setValue(2)
    s_exp.ovelap_spinBox.setValue(10)

    s_exp.add_ch_explorer_Button.click()
    assert s_exp.channel_explorer_tableWidget.rowCount() == 1

    s_exp.time_groupBox.setChecked(True)
    s_exp.timepoints_spinBox.setValue(2)
    s_exp.interval_spinBox.setValue(0)

    s_exp.stack_groupBox.setChecked(True)
    s_exp.z_tabWidget.setCurrentIndex(1)
    s_exp.zrange_spinBox.setValue(2)
    s_exp.step_size_doubleSpinBox.setValue(1.0)
    assert s_exp.n_images_label.text() == "Number of Images: 3"

    s_exp.stage_pos_groupBox.setChecked(True)
    s_exp.add_pos_Button.click()
    assert s_exp.stage_tableWidget.rowCount() == 1
    mmc.setXYPosition(2000.0, 2000.0)
    mmc.waitForSystem()
    s_exp.add_pos_Button.click()

    assert s_exp.stage_tableWidget.rowCount() == 2

    state = s_exp._get_state()

    sequence = MDASequence(
        channels=[
            {
                "config": "Cy5",
                "group": "Channel",
                "exposure": 100,
            }
        ],
        time_plan={"interval": {"milliseconds": 0}, "loops": 2},
        z_plan={"range": 2, "step": 1},
        axis_order="tpcz",
        stage_positions=(
            {"name": "Grid_001_Pos000", "x": -307.2, "y": 307.2, "z": 0.0},
            {"name": "Grid_001_Pos001", "x": 153.60000000000002, "y": 307.2, "z": 0.0},
            {
                "name": "Grid_001_Pos002",
                "x": 153.60000000000002,
                "y": -153.60000000000002,
                "z": 0.0,
            },
            {
                "name": "Grid_001_Pos003",
                "x": -307.2,
                "y": -153.60000000000002,
                "z": 0.0,
            },
            {
                "name": "Grid_002_Pos000",
                "x": 1692.7949999999998,
                "y": 2307.1949999999997,
                "z": 0.0,
            },
            {
                "name": "Grid_002_Pos001",
                "x": 2153.595,
                "y": 2307.1949999999997,
                "z": 0.0,
            },
            {
                "name": "Grid_002_Pos002",
                "x": 2153.595,
                "y": 1846.3949999999998,
                "z": 0.0,
            },
            {
                "name": "Grid_002_Pos003",
                "x": 1692.7949999999998,
                "y": 1846.3949999999998,
                "z": 0.0,
            },
        ),
    )

    assert state.channels == sequence.channels
    assert state.time_plan == sequence.time_plan
    assert state.z_plan == sequence.z_plan
    assert state.axis_order == sequence.axis_order
    assert state.stage_positions == sequence.stage_positions


def test_explorer_buttons(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = SampleExplorer()
    qtbot.addWidget(wdg)

    assert wdg.scan_size_spinBox_c.value() == 1
    assert wdg.scan_size_spinBox_r.value() == 1

    assert wdg.channel_explorer_tableWidget.rowCount() == 0
    wdg.add_ch_explorer_Button.click()
    wdg.add_ch_explorer_Button.click()
    assert wdg.channel_explorer_tableWidget.rowCount() == 2
    wdg.channel_explorer_tableWidget.selectRow(0)
    wdg.remove_ch_explorer_Button.click()
    assert wdg.channel_explorer_tableWidget.rowCount() == 1
    wdg.clear_ch_explorer_Button.click()
    assert wdg.channel_explorer_tableWidget.rowCount() == 0

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


def test_explorer_methods(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = SampleExplorer()
    qtbot.addWidget(wdg)

    wdg._on_mda_started()
    assert not wdg.time_groupBox.isEnabled()
    assert not wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_explorer_groupBox.isEnabled()
    assert not wdg.stage_pos_groupBox.isEnabled()
    assert not wdg.stack_groupBox.isEnabled()
    assert wdg.start_scan_Button.isHidden()
    assert not wdg.pause_scan_Button.isHidden()
    assert not wdg.cancel_scan_Button.isHidden()

    wdg._on_mda_finished()
    assert wdg.time_groupBox.isEnabled()
    assert wdg.acquisition_order_comboBox.isEnabled()
    assert wdg.channel_explorer_groupBox.isEnabled()
    assert wdg.stage_pos_groupBox.isEnabled()
    assert wdg.stack_groupBox.isEnabled()
    assert not wdg.start_scan_Button.isHidden()
    assert wdg.pause_scan_Button.isHidden()
    assert wdg.cancel_scan_Button.isHidden()


def test_gui_labels(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = SampleExplorer()
    qtbot.addWidget(wdg)

    assert wdg.channel_explorer_tableWidget.rowCount() == 0
    wdg.add_ch_explorer_Button.click()
    assert wdg.channel_explorer_tableWidget.rowCount() == 1
    assert wdg.channel_explorer_tableWidget.cellWidget(0, 1).value() == 100.0
    assert not wdg.time_groupBox.isChecked()

    txt = "Minimum total acquisition time: 100.0000 ms.\n"
    assert wdg._total_time_lbl.text() == txt

    assert not wdg.time_groupBox.isChecked()
    wdg.time_groupBox.setChecked(True)

    txt = (
        "Minimum total acquisition time: 100.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg._total_time_lbl.text() == txt

    wdg.timepoints_spinBox.setValue(3)
    txt = (
        "Minimum total acquisition time: 300.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg._total_time_lbl.text() == txt

    wdg.interval_spinBox.setValue(10)
    txt1 = (
        "Minimum total acquisition time: 300.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    txt2 = "Interval shorter than acquisition time per timepoint."
    assert wdg._total_time_lbl.text() == txt1
    assert wdg._time_lbl.text() == txt2

    wdg.interval_spinBox.setValue(200)
    txt1 = (
        "Minimum total acquisition time: 3.3383 min.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg._total_time_lbl.text() == txt1
