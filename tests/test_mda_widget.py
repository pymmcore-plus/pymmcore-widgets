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
    assert not wdg.time_groupbox.isChecked()

    wdg._set_enabled(False)
    assert not wdg.time_groupbox.isEnabled()
    assert not wdg.buttons_wdg.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_groupbox.isEnabled()
    assert not wdg.position_groupbox.isEnabled()
    assert not wdg.stack_groupbox.isEnabled()
    wdg._set_enabled(True)

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
    )
    wdg.set_state(sequence)
    assert wdg.position_groupbox._table.rowCount() == 3
    assert wdg.channel_groupbox._table.rowCount() == 2
    assert wdg.time_groupbox.isChecked()

    # round trip
    assert wdg.get_state() == sequence


def test_mda_buttons(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

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


def test_mda_methods(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
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
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    wdg.show()

    assert wdg.channel_groupbox._table.rowCount() == 0
    wdg.channel_groupbox._add_button.click()
    assert wdg.channel_groupbox._table.rowCount() == 1
    assert wdg.channel_groupbox._table.cellWidget(0, 1).value() == 100.0

    assert not wdg.time_groupbox.isChecked()
    wdg.time_groupbox.setChecked(True)
    wdg.time_groupbox._add_button.click()

    txt = (
        "Minimum total acquisition time: 100 ms"
        "\nMinimum acquisition time per timepoint: 100 ms"
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt
    assert not wdg.time_groupbox._warning_widget.isVisible()

    assert wdg.time_groupbox.isChecked()
    interval = cast("_DoubleSpinAndCombo", wdg.time_groupbox._table.cellWidget(0, 0))
    timepoint = cast("QSpinBox", wdg.time_groupbox._table.cellWidget(0, 1))
    interval.setValue(1, "ms")
    timepoint.setValue(2)
    assert wdg.time_groupbox._warning_widget.isVisible()

    txt = (
        "Minimum total acquisition time: 201 ms"
        "\nMinimum acquisition time per timepoint: 100 ms"
    )
    assert wdg.time_lbl._total_time_lbl.text() == txt

    wdg.channel_groupbox._add_button.click()
    wdg.channel_groupbox._advanced_cbox.setChecked(True)
    wdg.channel_groupbox._table.cellWidget(1, 4).setValue(2)
    wdg.channel_groupbox._table.cellWidget(1, 1).setValue(100.0)
    assert wdg.time_groupbox._warning_widget.isVisible()
    interval.setValue(200, "ms")
    timepoint.setValue(4)
    assert not wdg.time_groupbox._warning_widget.isVisible()

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


def test_grid_sequence_fov(qtbot: QtBot, global_mmcore: CMMCorePlus):
    """Test that the FOV size is updated when creating the MDASequernce."""
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    mmc = global_mmcore

    sequence = MDASequence(
        channels=[
            {"config": "FITC", "exposure": 50},
        ],
        stage_positions=(
            {
                "name": "Pos000",
                "x": 1,
                "y": 2,
                "z": 3,
                "sequence": {"grid_plan": {"rows": 2, "columns": 2}},
            },
        ),
    )

    wdg.set_state(sequence)

    assert wdg.get_state()._fov_size == (512.0, 512.0)
    mmc.setProperty("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    assert wdg.get_state()._fov_size == (256.0, 256.0)
    pos_seq = wdg.get_state().stage_positions[0].sequence
    assert pos_seq._fov_size == (256.0, 256.0)
