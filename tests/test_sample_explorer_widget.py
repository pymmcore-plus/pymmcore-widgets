from __future__ import annotations

from typing import TYPE_CHECKING

from useq import MDASequence

from pymmcore_widgets import SampleExplorerWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_explorer_state(qtbot: QtBot, global_mmcore: CMMCorePlus):
    # sourcery skip: remove-duplicate-set-key
    global_mmcore.setExposure(100)
    s_exp = SampleExplorerWidget(include_run_button=True)
    qtbot.add_widget(s_exp)
    mmc = global_mmcore

    assert len(s_exp._mmc.getLoadedDevices()) > 2
    assert mmc.getChannelGroup() == "Channel"

    s_exp.grid_params.scan_size_spinBox_c.setValue(2)
    s_exp.grid_params.scan_size_spinBox_r.setValue(2)
    s_exp.grid_params.overlap_spinBox.setValue(10)

    s_exp.channel_groupbox._add_button.click()
    assert s_exp.channel_groupbox._table.rowCount() == 1

    s_exp.time_groupbox.setChecked(True)
    s_exp.time_groupbox._timepoints_spinbox.setValue(2)
    s_exp.time_groupbox._interval_spinbox.setValue(0)

    s_exp.stack_groupbox.setChecked(True)
    s_exp.stack_groupbox.set_state({"range": 2, "step": 1})
    assert s_exp.stack_groupbox.n_images_label.text() == "Number of Images: 3"

    s_exp.position_groupbox.setChecked(True)
    s_exp.position_groupbox.add_button.click()
    assert s_exp.position_groupbox._table.rowCount() == 1
    mmc.setXYPosition(2000.0, 2000.0)
    mmc.waitForSystem()
    s_exp.position_groupbox.add_button.click()

    assert s_exp.position_groupbox._table.rowCount() == 2

    state = s_exp.get_state()

    p_seq = {
        "grid_plan": {
            "rows": 2,
            "columns": 2,
            "mode": "row_wise_snake",
            "overlap": (10.0, 10.0),
            "relative_to": "center",
        }
    }
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
        axis_order="tpgcz",
        stage_positions=(
            {
                "name": "Pos000",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "sequence": p_seq,
            },
            {
                "name": "Pos001",
                "x": 1999.99,
                "y": 1999.99,
                "z": 0.0,
                "sequence": p_seq,
            },
        ),
    )

    assert state.channels == sequence.channels
    assert state.time_plan == sequence.time_plan
    assert state.z_plan == sequence.z_plan
    assert state.axis_order == sequence.axis_order
    assert state.stage_positions == sequence.stage_positions


def p(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = SampleExplorerWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    assert wdg.grid_params.scan_size_spinBox_c.value() == 1
    assert wdg.grid_params.scan_size_spinBox_r.value() == 1

    assert wdg.channel_groupbox._table.rowCount() == 0
    wdg.channel_groupbox._add_button.click()
    wdg.channel_groupbox._add_button.click()
    assert wdg.channel_groupbox._table.rowCount() == 2
    wdg.channel_groupbox._table.selectRow(0)
    wdg.channel_groupbox._remove_button.click()
    assert wdg.channel_groupbox._table.rowCount() == 1
    wdg.channel_groupbox._clear_button.click()
    assert wdg.channel_groupbox._table.rowCount() == 0

    assert wdg.position_groupbox._table.rowCount() == 0
    wdg.position_groupbox.setChecked(True)
    wdg.position_groupbox.add_button.click()
    wdg.position_groupbox.add_button.click()
    assert wdg.position_groupbox._table.rowCount() == 2
    wdg.position_groupbox._table.selectRow(0)
    wdg.position_groupbox.remove_button.click()
    assert wdg.position_groupbox._table.rowCount() == 1
    wdg.position_groupbox.clear_button.click()
    assert wdg.position_groupbox._table.rowCount() == 0


def test_explorer_methods(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = SampleExplorerWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    wdg._on_mda_started()
    assert not wdg.time_groupbox.isEnabled()
    assert not wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupbox.isEnabled()
    assert not wdg.position_groupbox.isEnabled()
    assert not wdg.stack_groupbox.isEnabled()
    assert wdg.buttons_wdg.run_button.isHidden()
    assert not wdg.buttons_wdg.pause_button.isHidden()
    assert not wdg.buttons_wdg.cancel_button.isHidden()

    wdg._on_mda_finished()
    assert wdg.time_groupbox.isEnabled()
    assert wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert wdg.channel_groupbox.isEnabled()
    assert wdg.position_groupbox.isEnabled()
    assert wdg.stack_groupbox.isEnabled()
    assert not wdg.buttons_wdg.run_button.isHidden()
    assert wdg.buttons_wdg.pause_button.isHidden()
    assert wdg.buttons_wdg.cancel_button.isHidden()


def test_gui_labels(qtbot: QtBot, global_mmcore: CMMCorePlus):
    global_mmcore.setExposure(100)
    wdg = SampleExplorerWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    wdg.show()

    assert wdg.channel_groupbox._table.rowCount() == 0
    wdg.channel_groupbox._add_button.click()
    assert wdg.channel_groupbox._table.rowCount() == 1
    assert wdg.channel_groupbox._table.cellWidget(0, 1).value() == 100.0
    assert not wdg.time_groupbox.isChecked()
    assert not wdg.time_groupbox._warning_widget.isVisible()
    wdg.time_groupbox._units_combo.setCurrentText("ms")

    txt = "Minimum total acquisition time: 100.0000 ms.\n"
    assert wdg.time_lbl._total_time_lbl.text() == txt

    assert not wdg.time_groupbox.isChecked()
    wdg.time_groupbox.setChecked(True)
    assert wdg.time_groupbox._warning_widget.isVisible()

    txt = (
        "Minimum total acquisition time: 100.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt

    wdg.time_groupbox._timepoints_spinbox.setValue(3)
    txt = (
        "Minimum total acquisition time: 300.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt

    wdg.time_groupbox._interval_spinbox.setValue(10)
    txt1 = (
        "Minimum total acquisition time: 300.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt1

    wdg.time_groupbox._interval_spinbox.setValue(200)
    txt1 = (
        "Minimum total acquisition time: 500.0000 ms.\n"
        "Minimum acquisition time per timepoint: 100.0000 ms."
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt1
    assert not wdg.time_groupbox._warning_widget.isVisible()
