from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from useq import MDASequence

from pymmcore_widgets._mda import MDAWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot
    from qtpy.QtWidgets import QSpinBox

    from pymmcore_widgets._mda._time_plan_widget import _DoubleSpinAndCombo


def test_mda_widget_load_state(qtbot: QtBot):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    assert wdg.position_groupbox._table.rowCount() == 0
    assert wdg.channel_groupbox._table.rowCount() == 0
    assert not wdg.t_cbox.isChecked()

    wdg._enable_widgets(False)
    assert not wdg.time_groupbox.isEnabled()
    assert not wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupbox.isEnabled()
    assert not wdg.position_groupbox.isEnabled()
    assert not wdg.stack_groupbox.isEnabled()
    assert not wdg.grid_groupbox.isEnabled()
    wdg._enable_widgets(True)

    sequence = MDASequence(
        channels=[
            {"config": "Cy5", "exposure": 20},
            {"config": "FITC", "exposure": 50},
        ],
        time_plan={"phases": [{"interval": 2, "loops": 5}]},
        z_plan={"range": 4, "step": 0.5},
        axis_order="tpgcz",
        stage_positions=(
            {"name": "Pos000", "x": 222, "y": 1, "z": 1},
            {"name": "Pos001", "x": 111, "y": 0, "z": 0},
            {
                "name": "Pos002",
                "x": 1,
                "y": 2,
                "z": 3,
                "sequence": {
                    "grid_plan": {
                        "rows": 2,
                        "columns": 2,
                        "mode": "row_wise_snake",
                        "overlap": (0.0, 0.0),
                    },
                },
            },
        ),
        grid_plan={
            "rows": 1,
            "columns": 2,
            "mode": "row_wise_snake",
            "overlap": (0.0, 0.0),
        },
    )
    wdg.set_state(sequence)
    assert wdg.position_groupbox._table.rowCount() == 3
    assert wdg.channel_groupbox._table.rowCount() == 2
    assert wdg.t_cbox.isChecked()
    assert wdg.g_cbox.isChecked()

    # round trip
    assert wdg.get_state() == sequence


def test_mda_buttons(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    wdg.ch_cbox.setChecked(True)
    wdg.p_cbox.setChecked(True)
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
    wdg.position_groupbox.add_button.click()
    wdg.position_groupbox.add_button.click()
    assert wdg.position_groupbox._table.rowCount() == 2
    wdg.position_groupbox._table.selectRow(0)
    wdg.position_groupbox.remove_button.click()
    assert wdg.position_groupbox._table.rowCount() == 1
    wdg.position_groupbox.clear_button.click()
    assert wdg.position_groupbox._table.rowCount() == 0


def test_mda_methods(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    wdg.p_cbox.setChecked(True)
    wdg.z_cbox.setChecked(True)
    wdg.t_cbox.setChecked(True)

    wdg._on_mda_started()
    assert not wdg.time_groupbox.isEnabled()
    assert not wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupbox.isEnabled()
    assert not wdg.position_groupbox.isEnabled()
    assert not wdg.stack_groupbox.isEnabled()
    assert not wdg.grid_groupbox.isEnabled()
    assert wdg.buttons_wdg.run_button.isHidden()
    assert not wdg.buttons_wdg.pause_button.isHidden()
    assert not wdg.buttons_wdg.cancel_button.isHidden()

    wdg._on_mda_finished()
    assert wdg.time_groupbox.isEnabled()
    assert wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupbox.isEnabled()
    assert wdg.position_groupbox.isEnabled()
    assert wdg.stack_groupbox.isEnabled()
    assert not wdg.grid_groupbox.isEnabled()
    assert not wdg.buttons_wdg.run_button.isHidden()
    assert wdg.buttons_wdg.pause_button.isHidden()
    assert wdg.buttons_wdg.cancel_button.isHidden()


def test_gui_labels(qtbot: QtBot, global_mmcore: CMMCorePlus):
    # sourcery skip: extract-duplicate-method
    global_mmcore.setExposure(100)
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.ch_cbox.setChecked(True)
    assert wdg.channel_groupbox._table.rowCount() == 0
    wdg.channel_groupbox._add_button.click()
    assert wdg.channel_groupbox._table.rowCount() == 1
    assert wdg.channel_groupbox._table.cellWidget(0, 1).value() == 100.0

    assert not wdg.t_cbox.isChecked()
    wdg.t_cbox.setChecked(True)
    wdg.time_groupbox._add_button.click()

    txt = (
        "Minimum total acquisition time: 100 ms"
        "\nMinimum acquisition time per timepoint: 100 ms"
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt
    assert wdg.time_groupbox._warning_widget.isHidden()

    assert wdg.t_cbox.isChecked()
    interval = cast("_DoubleSpinAndCombo", wdg.time_groupbox._table.cellWidget(0, 0))
    timepoint = cast("QSpinBox", wdg.time_groupbox._table.cellWidget(0, 1))
    interval.setValue(1, "ms")
    timepoint.setValue(2)

    txt = (
        "Minimum total acquisition time: 201 ms"
        "\nMinimum acquisition time per timepoint: 100 ms"
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt
    assert not wdg.time_groupbox._warning_widget.isHidden()

    wdg.channel_groupbox._add_button.click()
    wdg.channel_groupbox._advanced_cbox.setChecked(True)
    wdg.channel_groupbox._table.cellWidget(1, 4).setValue(2)
    wdg.channel_groupbox._table.cellWidget(1, 1).setValue(100.0)
    assert not wdg.time_groupbox._warning_widget.isHidden()
    interval.setValue(200, "ms")
    timepoint.setValue(4)
    assert wdg.time_groupbox._warning_widget.isHidden()

    txt = (
        "Minimum total acquisition time: 01 sec 200 ms"
        "\nMinimum acquisition time per timepoint: 100 ms"
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt

    wdg.time_groupbox._add_button.click()
    timepoint = cast("QSpinBox", wdg.time_groupbox._table.cellWidget(1, 1))
    timepoint.setValue(2)

    txt = (
        "Minimum total acquisition time: 02 sec 400 ms"
        "\nMinimum acquisition time per timepoint: 100 ms"
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt


def test_enable_run_button(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    wdg.show()
    mmc = global_mmcore

    assert mmc.getChannelGroup() == "Channel"
    assert not mmc.getCurrentConfig("Channel")
    assert not wdg.buttons_wdg.run_button.isEnabled()
    assert not wdg.ch_cbox.isChecked()

    wdg.ch_cbox.setChecked(True)
    assert not wdg.buttons_wdg.run_button.isEnabled()
    wdg.channel_groupbox._add_button.click()
    assert wdg.channel_groupbox._table.rowCount()
    assert wdg.buttons_wdg.run_button.isEnabled()

    wdg.ch_cbox.setChecked(False)
    assert not wdg.buttons_wdg.run_button.isEnabled()

    mmc.setConfig("Channel", "DAPI")
    assert wdg.buttons_wdg.run_button.isEnabled()

    mmc.setChannelGroup("")
    assert not wdg.buttons_wdg.run_button.isEnabled()


def test_absolute_grid_warning(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    wdg.show()

    assert not wdg.g_cbox.isChecked()
    assert not wdg.p_cbox.isChecked()

    wdg.g_cbox.setChecked(True)
    wdg.grid_groupbox.tab.setCurrentIndex(1)

    wdg.p_cbox.setChecked(True)
    wdg.position_groupbox.add_button.click()
    wdg.position_groupbox.add_button.click()

    assert not wdg.grid_groupbox.tab.isTabEnabled(1)
    assert not wdg.grid_groupbox.tab.isTabEnabled(2)

    wdg.p_cbox.setChecked(False)

    assert wdg.grid_groupbox.tab.isTabEnabled(1)
    assert wdg.grid_groupbox.tab.isTabEnabled(2)
