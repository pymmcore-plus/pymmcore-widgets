from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional, Tuple, Union

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from useq import MDASequence

from .._util import ComboMessageBox
from ._grid_widget import GridWidget
from ._mda import SEQUENCE_META, SequenceMeta
from ._mda_gui import MultiDWidgetGui

if TYPE_CHECKING:
    from pymmcore_plus.mda import PMDAEngine


class MultiDWidget(MultiDWidgetGui):
    """Multi-dimensional acquisition Widget."""

    def __init__(
        self,
        parent: Optional[QtW.QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self.pause_Button.hide()
        self.cancel_Button.hide()

        self._mmc = mmcore or CMMCorePlus.instance()

        self.pause_Button.released.connect(lambda: self._mmc.mda.toggle_pause())
        self.cancel_Button.released.connect(lambda: self._mmc.mda.cancel())

        # connect buttons
        self.add_pos_Button.clicked.connect(self._add_position)
        self.remove_pos_Button.clicked.connect(self._remove_position)
        self.clear_pos_Button.clicked.connect(self._clear_positions)
        self.add_ch_Button.clicked.connect(self._add_channel)
        self.remove_ch_Button.clicked.connect(self._remove_channel)
        self.clear_ch_Button.clicked.connect(self._clear_channel)

        # self.browse_save_Button.clicked.connect(self._set_multi_d_acq_dir)
        self.run_Button.clicked.connect(self._on_run_clicked)

        self.grid_Button.clicked.connect(self._grid_widget)

        # connect for z stack
        self.set_top_Button.clicked.connect(self._set_top)
        self.set_bottom_Button.clicked.connect(self._set_bottom)
        self.z_top_doubleSpinBox.valueChanged.connect(self._update_topbottom_range)
        self.z_bottom_doubleSpinBox.valueChanged.connect(self._update_topbottom_range)

        self.zrange_spinBox.valueChanged.connect(self._update_rangearound_label)

        self.above_doubleSpinBox.valueChanged.connect(self._update_abovebelow_range)
        self.below_doubleSpinBox.valueChanged.connect(self._update_abovebelow_range)

        self.z_range_abovebelow_doubleSpinBox.valueChanged.connect(
            self._update_n_images
        )
        self.zrange_spinBox.valueChanged.connect(self._update_n_images)
        self.z_range_topbottom_doubleSpinBox.valueChanged.connect(self._update_n_images)
        self.step_size_doubleSpinBox.valueChanged.connect(self._update_n_images)
        self.z_tabWidget.currentChanged.connect(self._update_n_images)
        self.stack_groupBox.toggled.connect(self._update_n_images)

        # toggle connect
        # self.save_groupBox.toggled.connect(self._toggle_checkbox_save_pos)
        # self.stage_pos_groupBox.toggled.connect(self._toggle_checkbox_save_pos)
        self.time_groupBox.toggled.connect(self._calculate_total_time)
        self.stack_groupBox.toggled.connect(self._calculate_total_time)
        self.stage_pos_groupBox.toggled.connect(self._calculate_total_time)

        # connect position table double click
        self.stage_tableWidget.cellDoubleClicked.connect(self._move_to_position)

        # self.duration_spinBox.valueChanged.connect(
        #     self._on_duration_or_interval_changed
        # )
        # self.time_comboBox_1.currentIndexChanged.connect(
        #     self._on_duration_or_interval_changed
        # )
        # self.interval_spinBox.valueChanged.connect(
        #     self._on_duration_or_interval_changed
        # )
        # self.time_comboBox.currentIndexChanged.connect(self._on_timepoints_changed)
        # self.timepoints_spinBox.valueChanged.connect(self._on_timepoints_changed)

        # self.duration_spinBox.valueChanged.connect(self._calculate_total_time)
        self.interval_spinBox.valueChanged.connect(self._calculate_total_time)
        self.timepoints_spinBox.valueChanged.connect(self._calculate_total_time)

        # events
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)
        self._mmc.events.mdaEngineRegistered.connect(self._update_mda_engine)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        if channel_group := self._mmc.getChannelGroup() or self._guess_channel_group():
            self._mmc.setChannelGroup(channel_group)

    def _update_mda_engine(self, newEngine: PMDAEngine, oldEngine: PMDAEngine) -> None:
        oldEngine.events.sequenceStarted.disconnect(self._on_mda_started)
        oldEngine.events.sequenceFinished.disconnect(self._on_mda_finished)
        oldEngine.events.sequencePauseToggled.disconnect(self._on_mda_paused)

        newEngine.events.sequenceStarted.connect(self._on_mda_started)
        newEngine.events.sequenceFinished.connect(self._on_mda_finished)
        newEngine.events.sequencePauseToggled.connect(self._on_mda_paused)

    def _set_enabled(self, enabled: bool) -> None:
        # self.save_groupBox.setEnabled(enabled)
        self.time_groupBox.setEnabled(enabled)
        self.acquisition_order_comboBox.setEnabled(enabled)
        self.channel_groupBox.setEnabled(enabled)

        if not self._mmc.getXYStageDevice():
            self.stage_pos_groupBox.setChecked(False)
            self.stage_pos_groupBox.setEnabled(False)
        else:
            self.stage_pos_groupBox.setEnabled(enabled)

        if not self._mmc.getFocusDevice():
            self.stack_groupBox.setChecked(False)
            self.stack_groupBox.setEnabled(False)
        else:
            self.stack_groupBox.setEnabled(enabled)

    def _grid_widget(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        if not hasattr(self, "_grid_wdg"):
            self._grid_wdg = GridWidget(self)
            self._grid_wdg.sendPosList.connect(self._add_to_position_table)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_to_position_table(self, position_list: list, clear: bool) -> None:

        grid_number = 0

        if clear:
            self._clear_positions()
        else:
            for r in range(self.stage_tableWidget.rowCount()):
                pos_name = self.stage_tableWidget.item(r, 0).text()
                grid_name = pos_name.split("_")[0]
                if "Grid" in grid_name:
                    grid_n = grid_name[-3:]
                    if int(grid_n) > grid_number:
                        grid_number = int(grid_n)
            grid_number += 1

        for idx, position in enumerate(position_list):
            rows = self.stage_tableWidget.rowCount()
            self.stage_tableWidget.insertRow(rows)

            item = QtW.QTableWidgetItem(f"Grid{grid_number:03d}_Pos{idx:03d}")
            item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
            x = QtW.QTableWidgetItem(str(position[0]))
            x.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
            y = QtW.QTableWidgetItem(str(position[1]))
            y.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
            z = QtW.QTableWidgetItem(str(position[2]))
            z.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))

            self.stage_tableWidget.setItem(rows, 0, item)
            self.stage_tableWidget.setItem(rows, 1, x)
            self.stage_tableWidget.setItem(rows, 2, y)
            self.stage_tableWidget.setItem(rows, 3, z)

    def _set_top(self) -> None:
        self.z_top_doubleSpinBox.setValue(self._mmc.getZPosition())

    def _set_bottom(self) -> None:
        self.z_bottom_doubleSpinBox.setValue(self._mmc.getZPosition())

    def _update_topbottom_range(self) -> None:
        self.z_range_topbottom_doubleSpinBox.setValue(
            abs(self.z_top_doubleSpinBox.value() - self.z_bottom_doubleSpinBox.value())
        )

    def _update_rangearound_label(self, value: int) -> None:
        self.range_around_label.setText(f"-{value/2} µm <- z -> +{value/2} µm")

    def _update_abovebelow_range(self) -> None:
        self.z_range_abovebelow_doubleSpinBox.setValue(
            self.above_doubleSpinBox.value() + self.below_doubleSpinBox.value()
        )

    def _update_n_images(self) -> None:
        step = self.step_size_doubleSpinBox.value()
        # set what is the range to consider depending on the z_stack mode
        if self.z_tabWidget.currentIndex() == 0:
            _range = self.z_range_topbottom_doubleSpinBox.value()
        if self.z_tabWidget.currentIndex() == 1:
            _range = self.zrange_spinBox.value()
        if self.z_tabWidget.currentIndex() == 2:
            _range = self.z_range_abovebelow_doubleSpinBox.value()

        self.n_images_label.setText(f"Number of Images: {round((_range / step) + 1)}")
        self._calculate_total_time()

    def _time_in_sec(
        self, value: float, input_unit: Literal["ms", "min", "hours"]
    ) -> float:
        if input_unit == "ms":
            return value / 1000
        elif input_unit == "min":
            return value * 60
        elif input_unit == "hours":
            return value * 3600

    def _select_output_unit(self, duration: float) -> Tuple[float, str]:
        if duration < 1.0:
            return duration * 1000, "ms"
        elif duration < 60.0:
            return duration, "sec"
        elif duration < 3600.0:
            return duration / 60, "min"
        else:
            return duration / 3600, "hours"

    def _calculate_total_time(self) -> None:

        # channel
        exp: list = []
        ch = self.channel_tableWidget.rowCount()
        if ch > 0:
            exp.extend(
                self.channel_tableWidget.cellWidget(r, 1).value() for r in range(ch)
            )
        else:
            exp = []

        # time
        if self.time_groupBox.isChecked():
            timepoints = self.timepoints_spinBox.value()
            interval = self.interval_spinBox.value()
            int_unit = self.time_comboBox.currentText()
            if int_unit != "sec":
                interval = self._time_in_sec(interval, int_unit)
            tot_interval = interval * timepoints  # sec
        else:
            timepoints = 1
            tot_interval = 0

        # z stack
        if self.stack_groupBox.isChecked():
            n_z_images = int(self.n_images_label.text()[18:])
        else:
            n_z_images = 1

        # positions
        if self.stage_pos_groupBox.isChecked():
            n_pos = self.stage_tableWidget.rowCount() or 1
        else:
            n_pos = 1

        if not ch or not exp:
            self._total_time_lbl.setText(
                "Select at least one channel and exposure time."
            )
            return

        # total acq time
        t = 0  # ms
        for e in exp:
            t = t + (e * n_z_images * n_pos * timepoints)
        tot_time_sec = (t / 1000) + tot_interval  # sec
        tot_time, unit = self._select_output_unit(tot_time_sec)
        self._total_time_lbl.setText(
            f"Total Acquisition time: > {tot_time:.2f} {unit}."
        )

    def _on_mda_started(self) -> None:
        self._set_enabled(False)
        self.pause_Button.show()
        self.cancel_Button.show()
        self.run_Button.hide()

    def _on_mda_finished(self) -> None:
        self._set_enabled(True)
        self.pause_Button.hide()
        self.cancel_Button.hide()
        self.run_Button.show()

    def _on_mda_paused(self, paused: bool) -> None:
        self.pause_Button.setText("GO" if paused else "PAUSE")

    def _guess_channel_group(self) -> Union[str, None]:
        """Try to update the list of channel group choices.

        1. get a list of potential channel groups from pymmcore
        2. if there is only one, use it, if there are > 1, show a dialog box
        """
        candidates = self._mmc.getOrGuessChannelGroup()
        if len(candidates) == 1:
            return candidates[0]
        elif candidates:
            dialog = ComboMessageBox(candidates, "Select Channel Group:", self)
            if dialog.exec_() == dialog.DialogCode.Accepted:
                return dialog.currentText()
        return None

    def _add_channel(self) -> bool:
        """Add, remove or clear channel table.  Return True if anyting was changed."""
        if len(self._mmc.getLoadedDevices()) <= 1:
            return False

        channel_group = self._mmc.getChannelGroup()
        if not channel_group:
            return False

        idx = self.channel_tableWidget.rowCount()
        self.channel_tableWidget.insertRow(idx)

        # create a combo_box for channels in the table
        channel_comboBox = QtW.QComboBox(self)
        channel_exp_spinBox = QtW.QSpinBox(self)
        channel_exp_spinBox.setRange(0, 10000)
        channel_exp_spinBox.setValue(100)
        channel_exp_spinBox.valueChanged.connect(self._calculate_total_time)

        if channel_group := self._mmc.getChannelGroup():
            channel_list = list(self._mmc.getAvailableConfigs(channel_group))
            channel_comboBox.addItems(channel_list)

        self.channel_tableWidget.setCellWidget(idx, 0, channel_comboBox)
        self.channel_tableWidget.setCellWidget(idx, 1, channel_exp_spinBox)

        self._calculate_total_time()

        return True

    def _remove_channel(self) -> None:
        # remove selected position
        rows = {r.row() for r in self.channel_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.channel_tableWidget.removeRow(idx)

        self._calculate_total_time()

    def _clear_channel(self) -> None:
        # clear all positions
        self.channel_tableWidget.clearContents()
        self.channel_tableWidget.setRowCount(0)

        self._calculate_total_time()

    # def _toggle_checkbox_save_pos(self) -> None:
    #     if (
    #         self.stage_pos_groupBox.isChecked()
    #         and self.stage_tableWidget.rowCount() > 0
    #     ):
    #         self.checkBox_save_pos.setEnabled(True)

    #     else:
    #         self.checkBox_save_pos.setCheckState(Qt.CheckState.Unchecked)
    #         self.checkBox_save_pos.setEnabled(False)

    # add, remove, clear, move_to positions table
    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("PXYZ"):

                if ax == "P":
                    count = self.stage_tableWidget.rowCount() - 1
                    item = QtW.QTableWidgetItem(f"Pos{count:03d}")
                    item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                    self.stage_tableWidget.setItem(idx, c, item)
                    self._rename_positions(["Pos"])
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue
                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QtW.QTableWidgetItem(str(cur))
                item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                self.stage_tableWidget.setItem(idx, c, item)

            # self._toggle_checkbox_save_pos()
            self._calculate_total_time()

    def _add_position_row(self) -> int:
        idx = self.stage_tableWidget.rowCount()
        self.stage_tableWidget.insertRow(idx)
        return idx  # type: ignore [no-any-return]

    def _remove_position(self) -> None:
        # remove selected position
        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        removed = []
        for idx in sorted(rows, reverse=True):
            name = self.stage_tableWidget.item(idx, 0).text().split("_")[0]
            if "Pos" in name:
                if "Pos" not in removed:
                    removed.append("Pos")
            elif name not in removed:
                removed.append(name)
            self.stage_tableWidget.removeRow(idx)
        self._rename_positions(removed)
        # self._toggle_checkbox_save_pos()
        self._calculate_total_time()

    def _rename_positions(self, names: list) -> None:
        for name in names:
            grid_count = 0
            pos_count = 0
            for r in range(self.stage_tableWidget.rowCount()):
                start = self.stage_tableWidget.item(r, 0).text().split("_")[0]
                if start == name:  # Grid
                    new_name = f"{name}_Pos{grid_count:03d}"
                    grid_count += 1
                elif "Pos" in start:  # Pos
                    new_name = f"Pos{pos_count:03d}"
                    pos_count += 1
                else:
                    continue
                item = QtW.QTableWidgetItem(new_name)
                item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                self.stage_tableWidget.setItem(r, 0, item)

    def _clear_positions(self) -> None:
        # clear all positions
        self.stage_tableWidget.clearContents()
        self.stage_tableWidget.setRowCount(0)
        # self._toggle_checkbox_save_pos()
        self._calculate_total_time()

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self.stage_tableWidget.currentRow()
        x_val = self.stage_tableWidget.item(curr_row, 1).text()
        y_val = self.stage_tableWidget.item(curr_row, 2).text()
        z_val = self.stage_tableWidget.item(curr_row, 3).text()
        self._mmc.setXYPosition(float(x_val), float(y_val))
        self._mmc.setPosition(self._mmc.getFocusDevice(), float(z_val))

    # def _set_multi_d_acq_dir(self) -> None:
    #     # set the directory
    #     self.dir = QtW.QFileDialog(self)
    #     self.dir.setFileMode(QtW.QFileDialog.DirectoryOnly)
    #     self.save_dir = QtW.QFileDialog.getExistingDirectory(self.dir)
    #     self.dir_lineEdit.setText(self.save_dir)
    #     self.parent_path = Path(self.save_dir)

    def set_state(self, state: dict | MDASequence | str | Path) -> None:
        """Set current state of MDA widget.

        Parameters
        ----------
        state : Union[dict, MDASequence, str, Path]
            MDASequence state in the form of a dict, MDASequence object, or a str or
            Path pointing to a sequence.yaml file
        """
        if isinstance(state, (str, Path)):
            state = MDASequence.parse_file(state)
        elif isinstance(state, dict):
            state = MDASequence(**state)
        if not isinstance(state, MDASequence):
            raise TypeError("state must be an MDASequence, dict, or yaml file")

        self.acquisition_order_comboBox.setCurrentText(state.axis_order)

        # set channel table
        self._clear_channel()
        if channel_group := self._mmc.getChannelGroup():
            channel_list = list(self._mmc.getAvailableConfigs(channel_group))
        else:
            channel_list = []
        for idx, ch in enumerate(state.channels):
            if not self._add_channel():
                break
            if ch.config in channel_list:
                self.channel_tableWidget.cellWidget(idx, 0).setCurrentText(ch.config)
            else:
                warnings.warn(
                    f"Unrecognized channel: {ch.config!r}. "
                    f"Valid channels include {channel_list}"
                )
            if ch.exposure:
                self.channel_tableWidget.cellWidget(idx, 1).setValue(int(ch.exposure))

        # set Z
        if state.z_plan:
            self.stack_groupBox.setChecked(True)
            if hasattr(state.z_plan, "top") and hasattr(state.z_plan, "bottom"):
                self.z_top_doubleSpinBox.setValue(state.z_plan.top)
                self.z_bottom_doubleSpinBox.setValue(state.z_plan.bottom)
                self.z_tabWidget.setCurrentIndex(0)
            elif hasattr(state.z_plan, "above") and hasattr(state.z_plan, "below"):
                self.above_doubleSpinBox.setValue(state.z_plan.above)
                self.below_doubleSpinBox.setValue(state.z_plan.below)
                self.z_tabWidget.setCurrentIndex(2)
            elif hasattr(state.z_plan, "range"):
                self.zrange_spinBox.setValue(int(state.z_plan.range))
                self.z_tabWidget.setCurrentIndex(1)
            if hasattr(state.z_plan, "step"):
                self.step_size_doubleSpinBox.setValue(state.z_plan.step)
        else:
            self.stack_groupBox.setChecked(False)

        # set time
        # currently only `TIntervalLoops` is supported
        if hasattr(state.time_plan, "interval") and hasattr(state.time_plan, "loops"):
            self.time_groupBox.setChecked(True)
            self.timepoints_spinBox.setValue(state.time_plan.loops)

            sec = state.time_plan.interval.total_seconds()
            if sec >= 60:
                self.time_comboBox.setCurrentText("min")
                self.interval_spinBox.setValue(sec // 60)
            elif sec >= 1:
                self.time_comboBox.setCurrentText("sec")
                self.interval_spinBox.setValue(int(sec))
            else:
                self.time_comboBox.setCurrentText("ms")
                self.interval_spinBox.setValue(int(sec * 1000))
        else:
            self.time_groupBox.setChecked(False)

        # set stage positions
        self._clear_positions()
        if state.stage_positions:
            self.stage_pos_groupBox.setChecked(True)
            for idx, pos in enumerate(state.stage_positions):
                self._add_position_row()
                for c, ax in enumerate("pxyz"):
                    if ax == "p":
                        pos_name = pos.name or f"Pos{idx:03d}"
                        item = QtW.QTableWidgetItem(str(pos_name))
                    else:
                        item = QtW.QTableWidgetItem(str(getattr(pos, ax)))
                    item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                    self.stage_tableWidget.setItem(idx, c, item)
        else:
            self.stage_pos_groupBox.setChecked(False)

    def _get_state(self) -> MDASequence:
        """Get current state of widget as a useq.MDASequence."""
        state = {
            "axis_order": self.acquisition_order_comboBox.currentText(),
            "channels": [],
            "stage_positions": [],
            "z_plan": None,
            "time_plan": None,
        }
        state["channels"] = [
            {
                "config": self.channel_tableWidget.cellWidget(c, 0).currentText(),
                "group": self._mmc.getChannelGroup() or "Channel",
                "exposure": self.channel_tableWidget.cellWidget(c, 1).value(),
            }
            for c in range(self.channel_tableWidget.rowCount())
        ]
        if self.stack_groupBox.isChecked():

            if self.z_tabWidget.currentIndex() == 0:
                state["z_plan"] = {
                    "top": self.z_top_doubleSpinBox.value(),
                    "bottom": self.z_bottom_doubleSpinBox.value(),
                    "step": self.step_size_doubleSpinBox.value(),
                }

            elif self.z_tabWidget.currentIndex() == 1:
                state["z_plan"] = {
                    "range": self.zrange_spinBox.value(),
                    "step": self.step_size_doubleSpinBox.value(),
                }
            elif self.z_tabWidget.currentIndex() == 2:
                state["z_plan"] = {
                    "above": self.above_doubleSpinBox.value(),
                    "below": self.below_doubleSpinBox.value(),
                    "step": self.step_size_doubleSpinBox.value(),
                }

        if self.time_groupBox.isChecked():
            unit = {"min": "minutes", "sec": "seconds", "ms": "milliseconds"}[
                self.time_comboBox.currentText()
            ]
            state["time_plan"] = {
                "interval": {unit: self.interval_spinBox.value()},
                "loops": self.timepoints_spinBox.value(),
            }
        # position settings
        if self._mmc.getXYStageDevice():
            if (
                self.stage_pos_groupBox.isChecked()
                and self.stage_tableWidget.rowCount() > 0
            ):
                for r in range(self.stage_tableWidget.rowCount()):
                    pos = {
                        "name": self.stage_tableWidget.item(r, 0).text(),
                        "x": float(self.stage_tableWidget.item(r, 1).text()),
                        "y": float(self.stage_tableWidget.item(r, 2).text()),
                    }
                    if self._mmc.getFocusDevice():
                        pos["z"] = float(self.stage_tableWidget.item(r, 3).text())
                    state["stage_positions"].append(pos)
            else:
                pos = {
                    "name": "Pos_000",
                    "x": float(self._mmc.getXPosition()),
                    "y": float(self._mmc.getYPosition()),
                }
                if self._mmc.getFocusDevice():
                    pos["z"] = float(self._mmc.getZPosition())
                state["stage_positions"].append(pos)

        return MDASequence(**state)

    def _on_run_clicked(self) -> None:

        if len(self._mmc.getLoadedDevices()) < 2:
            raise ValueError("Load a cfg file first.")

        if self.channel_tableWidget.rowCount() <= 0:
            raise ValueError("Select at least one channel.")

        if self.stage_pos_groupBox.isChecked() and (
            self.stage_tableWidget.rowCount() <= 0
        ):
            raise ValueError(
                "Select at least one position" "or deselect the position groupbox."
            )

        # if self.save_groupBox.isChecked() and not (
        #     self.fname_lineEdit.text() and Path(self.dir_lineEdit.text()).is_dir()
        # ):
        #     raise ValueError("Select a filename and a valid directory.")

        experiment = self._get_state()

        SEQUENCE_META[experiment] = SequenceMeta(
            mode="mda",
            split_channels=self.checkBox_split_channels.isChecked(),
            # should_save=self.save_groupBox.isChecked(),
            # file_name=self.fname_lineEdit.text(),
            # save_dir=self.dir_lineEdit.text(),
            # save_pos=self.checkBox_save_pos.isChecked(),
        )
        self._mmc.run_mda(experiment)  # run the MDA experiment asynchronously
        return
