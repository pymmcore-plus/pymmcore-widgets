from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from qtpy.QtWidgets import QFileDialog
from useq import MDASequence

from pymmcore_widgets._mda import MDAWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_mda_widget_load_state(qtbot: QtBot) -> None:
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)
    assert wdg.position_widget._table.rowCount() == 0
    assert wdg.channel_widget._table.rowCount() == 0
    assert not wdg.t_cbox.isChecked()

    wdg._enable_widgets(False)
    assert not wdg.time_widget.isEnabled()
    assert not wdg.acquisition_order_widget.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_widget.isEnabled()
    assert not wdg.position_widget.isEnabled()
    assert not wdg.stack_widget.isEnabled()
    assert not wdg.grid_widget.isEnabled()
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
            {
                "name": "Pos001",
                "x": 222,
                "y": 1,
                "z": 5,
                "sequence": {
                    "autofocus_plan": {
                        "autofocus_device_name": "Z",
                        "axes": ("t", "p", "g"),
                        "autofocus_motor_offset": 10.0,
                    }
                },
            },
            {
                "name": "Pos002",
                "x": 111,
                "y": 0,
                "z": 15,
                "sequence": {
                    "grid_plan": {
                        "rows": 2,
                        "columns": 2,
                        "fov_height": 512,
                        "fov_width": 512,
                    },
                    "autofocus_plan": {
                        "autofocus_device_name": "Z",
                        "axes": ("t", "p", "g"),
                        "autofocus_motor_offset": 10.0,
                    },
                },
            },
            {
                "name": "Pos003",
                "x": 1,
                "y": 2,
                "z": 3,
                "sequence": {
                    "grid_plan": {
                        "rows": 2,
                        "columns": 2,
                        "fov_height": 512,
                        "fov_width": 512,
                        "mode": "row_wise_snake",
                        "overlap": (0.0, 0.0),
                    },
                },
            },
        ),
        grid_plan={
            "rows": 1,
            "columns": 2,
            "fov_height": 512,
            "fov_width": 512,
            "mode": "row_wise_snake",
            "overlap": (0.0, 0.0),
        },
    )
    mocks = []
    for subcomponent in [
        wdg.time_widget,
        wdg.stack_widget,
        wdg.position_widget,
        wdg.channel_widget,
        wdg.grid_widget,
    ]:
        mocks.append(MagicMock())
        subcomponent.valueChanged.connect(mocks[-1])
    wdg.set_state(sequence)
    for mock in mocks:
        mock.assert_called_once()
    assert wdg.position_widget._table.rowCount() == 4
    assert wdg.channel_widget._table.rowCount() == 2
    assert wdg.t_cbox.isChecked()
    assert wdg.g_cbox.isChecked()

    # round trip
    assert wdg.get_state() == sequence


def test_mda_buttons(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    wdg.ch_cbox.setChecked(True)
    wdg.p_cbox.setChecked(True)
    assert wdg.channel_widget._table.rowCount() == 0
    wdg.channel_widget._add_button.click()
    wdg.channel_widget._add_button.click()
    assert wdg.channel_widget._table.rowCount() == 2
    wdg.channel_widget._table.selectRow(0)
    wdg.channel_widget._remove_button.click()
    assert wdg.channel_widget._table.rowCount() == 1
    wdg.channel_widget._clear_button.click()
    assert wdg.channel_widget._table.rowCount() == 0

    assert wdg.position_widget._table.rowCount() == 0
    wdg.position_widget.add_button.click()
    wdg.position_widget.add_button.click()
    assert wdg.position_widget._table.rowCount() == 2
    wdg.position_widget._table.selectRow(0)
    wdg.position_widget.remove_button.click()
    assert wdg.position_widget._table.rowCount() == 1
    wdg.position_widget.clear_button.click()
    assert wdg.position_widget._table.rowCount() == 0


def test_mda_methods(qtbot: QtBot):
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    wdg.p_cbox.setChecked(True)
    wdg.z_cbox.setChecked(True)
    wdg.t_cbox.setChecked(True)

    wdg._on_mda_started()
    wdg.buttons_wdg._on_mda_started()
    assert not wdg.time_widget.isEnabled()
    assert not wdg.acquisition_order_widget.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_widget.isEnabled()
    assert not wdg.position_widget.isEnabled()
    assert not wdg.stack_widget.isEnabled()
    assert not wdg.grid_widget.isEnabled()
    assert not wdg.buttons_wdg.pause_button.isHidden()
    assert not wdg.buttons_wdg.cancel_button.isHidden()
    assert wdg.buttons_wdg.run_button.isHidden()

    wdg._on_mda_finished()
    wdg.buttons_wdg._on_mda_finished()
    assert wdg.time_widget.isEnabled()
    assert wdg.acquisition_order_widget.acquisition_order_comboBox.isEnabled()
    assert not wdg.channel_widget.isEnabled()
    assert wdg.position_widget.isEnabled()
    assert wdg.stack_widget.isEnabled()
    assert not wdg.grid_widget.isEnabled()
    assert not wdg.buttons_wdg.run_button.isHidden()
    assert wdg.buttons_wdg.pause_button.isHidden()
    assert wdg.buttons_wdg.cancel_button.isHidden()


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
    wdg.channel_widget._add_button.click()
    assert wdg.channel_widget._table.rowCount()
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
    wdg.grid_widget.tab.setCurrentIndex(1)

    wdg.p_cbox.setChecked(True)
    wdg.position_widget.add_button.click()
    wdg.position_widget.add_button.click()

    assert not wdg.grid_widget.tab.isTabEnabled(1)
    assert not wdg.grid_widget.tab.isTabEnabled(2)

    wdg.p_cbox.setChecked(False)

    assert wdg.grid_widget.tab.isTabEnabled(1)
    assert wdg.grid_widget.tab.isTabEnabled(2)


def test_save_and_load_sequence(qtbot: QtBot):
    with tempfile.TemporaryDirectory() as tmp:

        def _path(*args, **kwargs):
            return Path(tmp) / "sequence.json", None

        with patch.object(QFileDialog, "getSaveFileName", _path):
            mda = MDAWidget()
            qtbot.addWidget(mda)

            seq = MDASequence(
                axis_order="tpgcz",
                stage_positions=[
                    {
                        "x": 10,
                        "y": 20,
                        "z": 50,
                        "name": "test_name",
                        "sequence": MDASequence(
                            grid_plan={
                                "rows": 2,
                                "columns": 3,
                                "fov_height": 512,
                                "fov_width": 512,
                            }
                        ),
                    },
                ],
                channels=[
                    {"config": "Cy5", "exposure": 50},
                    {
                        "config": "DAPI",
                        "exposure": 100.0,
                        "do_stack": False,
                        "acquire_every": 3,
                    },
                ],
                time_plan=[{"interval": 3, "loops": 3}, {"interval": 5, "loops": 10}],
                z_plan={"range": 1.0, "step": 0.5},
                grid_plan={
                    "rows": 2,
                    "columns": 1,
                    "fov_height": 512,
                    "fov_width": 512,
                },
            )
            mda.set_state(seq)

            mda._save_sequence()

            with patch.object(QFileDialog, "getOpenFileName", _path):
                mda._load_sequence()
                assert mda.get_state() == seq


def test_set_state_without_xystage(global_mmcore: CMMCorePlus, qtbot: QtBot):
    mmc = global_mmcore
    mmc.unloadDevice("XY")
    mmc.unloadDevice("Z")
    wdg = MDAWidget(include_run_button=True)
    qtbot.addWidget(wdg)

    p_table = wdg.position_widget._table
    mda = MDASequence(stage_positions=[(10, 20, 30)])
    wdg.set_state(mda)

    assert p_table.rowCount() == 1
    assert not mmc.getXYStageDevice()
    assert not mmc.getFocusDevice()
    assert wdg.get_state().stage_positions[0].x == 10
    assert wdg.get_state().stage_positions[0].y == 20
    assert wdg.get_state().stage_positions[0].z == 30
