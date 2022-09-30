from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional, Tuple, Union

import useq
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QSize, Qt
from superqt.fonticon import icon
from useq import MDASequence

from .._util import ComboMessageBox
from ._sample_explorer_gui import ExplorerGui

if TYPE_CHECKING:
    from pymmcore_plus.mda import PMDAEngine


class SampleExplorer(ExplorerGui):
    """Widget to create/run tiled acquisitions."""

    def __init__(
        self,
        parent: QtW.QWidget = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self.t0 = 0
        self.t1 = 0

        self.cancel_scan_Button.hide()
        self.pause_scan_Button.hide()

        self._mmc = mmcore or CMMCorePlus.instance()

        self.pixel_size = self._mmc.getPixelSizeUm()

        self.return_to_position_x = None
        self.return_to_position_y = None

        # connect for channel
        self.add_ch_explorer_Button.clicked.connect(self._add_channel)
        self.remove_ch_explorer_Button.clicked.connect(self._remove_channel)
        self.clear_ch_explorer_Button.clicked.connect(self._clear_channel)

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

        # connect for positions
        self.add_pos_Button.clicked.connect(self._add_position)
        self.remove_pos_Button.clicked.connect(self._remove_position)
        self.clear_pos_Button.clicked.connect(self._clear_positions)
        self.stage_tableWidget.cellDoubleClicked.connect(self._move_to_position)

        # connect buttons
        self.start_scan_Button.clicked.connect(self._start_scan)
        self.cancel_scan_Button.clicked.connect(self._mmc.mda.cancel)
        self.pause_scan_Button.clicked.connect(lambda: self._mmc.mda.toggle_pause())

        # connect toggle
        self.time_groupBox.toggled.connect(self._calculate_total_time)
        self.interval_spinBox.valueChanged.connect(self._calculate_total_time)
        self.timepoints_spinBox.valueChanged.connect(self._calculate_total_time)
        self.stack_groupBox.toggled.connect(self._calculate_total_time)
        self.stage_pos_groupBox.toggled.connect(self._calculate_total_time)

        self.scan_size_spinBox_r.valueChanged.connect(self._calculate_total_time)
        self.scan_size_spinBox_c.valueChanged.connect(self._calculate_total_time)

        self.time_comboBox.currentIndexChanged.connect(self._calculate_total_time)

        # connect mmcore signals
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

        self._mmc.events.mdaEngineRegistered.connect(self._update_mda_engine)

        self._on_sys_cfg_loaded()

    def _update_mda_engine(self, newEngine: PMDAEngine, oldEngine: PMDAEngine) -> None:
        oldEngine.events.sequenceStarted.disconnect(self._on_mda_started)
        oldEngine.events.sequenceFinished.disconnect(self._on_mda_finished)

        newEngine.events.sequenceStarted.connect(self._on_mda_started)
        newEngine.events.sequenceFinished.connect(self._on_mda_finished)

    def _on_sys_cfg_loaded(self) -> None:
        self.pixel_size = self._mmc.getPixelSizeUm()
        if channel_group := self._mmc.getChannelGroup() or self._guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self._clear_channel()

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

    def _on_mda_started(self, sequence: useq.MDASequence) -> None:
        """Block gui when mda starts."""
        self._set_enabled(False)
        self.cancel_scan_Button.show()
        self.pause_scan_Button.show()
        self.start_scan_Button.hide()

    def _on_mda_finished(self, sequence: useq.MDASequence) -> None:

        if not hasattr(self, "return_to_position_x"):
            return

        if (
            self.return_to_position_x is not None
            and self.return_to_position_y is not None
        ):
            self._mmc.setXYPosition(
                self.return_to_position_x, self.return_to_position_y
            )
            self.return_to_position_x = None
            self.return_to_position_y = None

        self._set_enabled(True)
        self.cancel_scan_Button.hide()
        self.pause_scan_Button.hide()
        self.start_scan_Button.show()

    def _set_enabled(self, enabled: bool) -> None:
        self.scan_size_spinBox_r.setEnabled(enabled)
        self.scan_size_spinBox_c.setEnabled(enabled)
        self.ovelap_spinBox.setEnabled(enabled)
        self.start_scan_Button.setEnabled(enabled)
        self.channel_explorer_groupBox.setEnabled(enabled)

    def _add_channel(self) -> bool:
        """Add, remove or clear channel table.  Return True if anyting was changed."""
        if len(self._mmc.getLoadedDevices()) <= 1:
            return False

        channel_group = self._mmc.getChannelGroup()
        if not channel_group:
            return False

        idx = self.channel_explorer_tableWidget.rowCount()
        self.channel_explorer_tableWidget.insertRow(idx)

        # create a combo_box for channels in the table
        self.channel_explorer_comboBox = QtW.QComboBox(self)
        self.channel_explorer_exp_spinBox = QtW.QSpinBox(self)
        self.channel_explorer_exp_spinBox.setRange(0, 10000)
        self.channel_explorer_exp_spinBox.setValue(100)
        self.channel_explorer_exp_spinBox.valueChanged.connect(
            self._calculate_total_time
        )

        if channel_group := self._mmc.getChannelGroup():
            channel_list = list(self._mmc.getAvailableConfigs(channel_group))
            self.channel_explorer_comboBox.addItems(channel_list)

        self.channel_explorer_tableWidget.setCellWidget(
            idx, 0, self.channel_explorer_comboBox
        )
        self.channel_explorer_tableWidget.setCellWidget(
            idx, 1, self.channel_explorer_exp_spinBox
        )

        self._calculate_total_time()

        return True

    def _remove_channel(self) -> None:
        # remove selected position
        rows = {r.row() for r in self.channel_explorer_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.channel_explorer_tableWidget.removeRow(idx)

        self._calculate_total_time()

    def _clear_channel(self) -> None:
        # clear all positions
        self.channel_explorer_tableWidget.clearContents()
        self.channel_explorer_tableWidget.setRowCount(0)

        self._calculate_total_time()

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

    # add, remove, clear, move_to positions table
    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("GXYZ"):
                if ax == "G":
                    count = self.stage_tableWidget.rowCount()
                    item = QtW.QTableWidgetItem(f"Grid_{count:03d}")
                    item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                    self.stage_tableWidget.setItem(idx, c, item)
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue

                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QtW.QTableWidgetItem(str(cur))
                item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                self.stage_tableWidget.setItem(idx, c, item)

        self._calculate_total_time()

    def _add_position_row(self) -> int:
        idx = int(self.stage_tableWidget.rowCount())
        self.stage_tableWidget.insertRow(idx)
        return idx

    def _remove_position(self) -> None:
        # remove selected position
        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.stage_tableWidget.removeRow(idx)

        self._calculate_total_time()

    def _clear_positions(self) -> None:
        # clear all positions
        self.stage_tableWidget.clearContents()
        self.stage_tableWidget.setRowCount(0)

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

        tiles = self.scan_size_spinBox_r.value() * self.scan_size_spinBox_c.value()

        # channel
        exp: list = []
        ch = self.channel_explorer_tableWidget.rowCount()
        if ch > 0:
            exp.extend(
                self.channel_explorer_tableWidget.cellWidget(r, 1).value()
                for r in range(ch)
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
        else:
            timepoints = 1
            interval = -1.0

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
        n_pos = n_pos

        # acq time per timepoint
        time_chs: float = 0.0  # s
        for e in exp:
            time_chs = time_chs + ((e / 1000) * n_z_images * n_pos * tiles)

        warning_msg = ""
        interval_msg = ""

        min_aq_tp, unit_1 = self._select_output_unit(time_chs)

        if interval <= 0:
            effective_interval = 0.0
            addition_time = 0
            _icon = None
            stylesheet = ""
            if interval == 0:
                interval_msg = (
                    f"Estimated minimum time interval:" f" {min_aq_tp:.4f} {unit_1}."
                )

        elif interval < time_chs:
            addition_time = 0
            effective_interval = 0.0
            warning_msg = "Interval shorter than acquisition time per timepoint."
            _icon = icon(MDI6.exclamation_thick, color="magenta").pixmap(QSize(30, 30))
            stylesheet = "color:magenta"

        else:
            effective_interval, unit_3 = self._select_output_unit(
                float(interval) - time_chs
            )

            addition_time = effective_interval * timepoints
            interval_msg = (
                f"Estimated minimum time interval:"
                f" {effective_interval:.4f} {unit_3}."
            )
            _icon = None
            stylesheet = ""

        min_tot_time, unit_4 = self._select_output_unit(
            (time_chs * timepoints) + addition_time - effective_interval
        )

        self._icon_lbl.clear()
        self._time_lbl.clear()
        self._time_lbl.setStyleSheet(stylesheet)
        if _icon:
            self._icon_lbl.setPixmap(_icon)
            self._time_lbl.show()
            self._time_lbl.setText(f"{warning_msg}")
            self._time_lbl.adjustSize()
        else:
            self._icon_lbl.setText(f"{interval_msg}")
            self._time_lbl.hide()

        t_per_tp_msg = ""
        tot_acq_msg = f"Minimum total acquisition time: {min_tot_time:.4f} {unit_4}.\n"
        if self.time_groupBox.isChecked():
            t_per_tp_msg = (
                f"Minimum acquisition time per timepoint: {min_aq_tp:.4f} {unit_1}."
            )
        self._total_time_lbl.setText(f"{tot_acq_msg}{t_per_tp_msg}")

    def _get_state(self) -> MDASequence:  # sourcery skip: merge-dict-assign

        table = self.channel_explorer_tableWidget

        state = {
            "axis_order": "tpzc",
            "channels": [],
            "stage_positions": [],
            "z_plan": None,
            "time_plan": None,
        }

        state["channels"] = [
            {  # type: ignore
                "config": table.cellWidget(c, 0).currentText(),
                "group": self._mmc.getChannelGroup() or "Channel",
                "exposure": table.cellWidget(c, 1).value(),
            }
            for c in range(table.rowCount())
        ]

        if self.stack_groupBox.isChecked():

            if self.z_tabWidget.currentIndex() == 0:
                state["z_plan"] = {  # type: ignore
                    "top": self.z_top_doubleSpinBox.value(),
                    "bottom": self.z_bottom_doubleSpinBox.value(),
                    "step": self.step_size_doubleSpinBox.value(),
                }

            elif self.z_tabWidget.currentIndex() == 1:
                state["z_plan"] = {  # type: ignore
                    "range": self.zrange_spinBox.value(),
                    "step": self.step_size_doubleSpinBox.value(),
                }
            elif self.z_tabWidget.currentIndex() == 2:
                state["z_plan"] = {  # type: ignore
                    "above": self.above_doubleSpinBox.value(),
                    "below": self.below_doubleSpinBox.value(),
                    "step": self.step_size_doubleSpinBox.value(),
                }

        if self.time_groupBox.isChecked():
            unit = {"min": "minutes", "sec": "seconds", "ms": "milliseconds"}[
                self.time_comboBox.currentText()
            ]
            state["time_plan"] = {  # type: ignore
                "interval": {unit: self.interval_spinBox.value()},
                "loops": self.timepoints_spinBox.value(),
            }

        for g in self._set_grid():
            pos = {"name": g[0], "x": g[1], "y": g[2]}
            if len(g) == 4:
                pos["z"] = g[3]
            state["stage_positions"].append(pos)  # type: ignore

        return MDASequence(**state)

    def _set_grid(self) -> list[tuple[str, float, float, Optional[float]]]:

        self.scan_size_r = self.scan_size_spinBox_r.value()
        self.scan_size_c = self.scan_size_spinBox_c.value()
        self.pixel_size = self._mmc.getPixelSizeUm()

        explorer_starting_positions = []
        if (
            self.stage_pos_groupBox.isChecked()
            and self.stage_tableWidget.rowCount() > 0
        ):
            for r in range(self.stage_tableWidget.rowCount()):
                name = self.stage_tableWidget.item(r, 0).text()
                x = float(self.stage_tableWidget.item(r, 1).text())
                y = float(self.stage_tableWidget.item(r, 2).text())
                z = float(self.stage_tableWidget.item(r, 3).text())
                pos_info = (
                    (name, x, y, z) if self._mmc.getFocusDevice() else (name, x, y)
                )
                explorer_starting_positions.append(pos_info)

        else:
            name = "Grid_001"
            x = float(self._mmc.getXPosition())
            y = float(self._mmc.getYPosition())
            if self._mmc.getFocusDevice():
                z = float(self._mmc.getZPosition())
                pos_info = (name, x, y, z)
            else:
                pos_info = (name, x, y)
            explorer_starting_positions.append(pos_info)

        full_pos_list = []
        for pe in explorer_starting_positions:

            name, x_pos, y_pos = pe[0], pe[1], pe[2]
            if self._mmc.getFocusDevice():
                z_pos = pe[3]

            self.return_to_position_x = x_pos
            self.return_to_position_y = y_pos

            # calculate initial scan position
            _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())

            overlap_percentage = self.ovelap_spinBox.value()
            overlap_px_w = width - (width * overlap_percentage) / 100
            overlap_px_h = height - (height * overlap_percentage) / 100

            if self.scan_size_r == 1 and self.scan_size_c == 1:
                raise ValueError(
                    "RxC -> 1x1. Use MDA to acquire a single position image."
                )

            move_x = (width / 2) * (self.scan_size_c - 1) - overlap_px_w
            move_y = (height / 2) * (self.scan_size_r - 1) - overlap_px_h

            # to match position coordinates with center of the image
            x_pos -= self.pixel_size * (move_x + width)
            y_pos += self.pixel_size * (move_y + height)

            # calculate position increments depending on pixle size
            if overlap_percentage > 0:
                increment_x = overlap_px_w * self.pixel_size
                increment_y = overlap_px_h * self.pixel_size
            else:
                increment_x = width * self.pixel_size
                increment_y = height * self.pixel_size

            list_pos_order = []
            pos_count = 0
            for r in range(self.scan_size_r):
                if r % 2:  # for odd rows
                    col = self.scan_size_c - 1
                    for c in range(self.scan_size_c):
                        if c == 0:
                            y_pos -= increment_y
                        pos_name = f"{name}_Pos{pos_count:03d}"
                        if self._mmc.getFocusDevice():
                            list_pos_order.append((pos_name, x_pos, y_pos, z_pos))
                        else:
                            list_pos_order.append(
                                (pos_name, x_pos, y_pos)  # type: ignore
                            )
                        if col > 0:
                            col -= 1
                            x_pos -= increment_x
                        pos_count += 1
                else:  # for even rows
                    for c in range(self.scan_size_c):
                        if r > 0 and c == 0:
                            y_pos -= increment_y
                        pos_name = f"{name}_Pos{pos_count:03d}"
                        if self._mmc.getFocusDevice():
                            list_pos_order.append((pos_name, x_pos, y_pos, z_pos))
                        else:
                            list_pos_order.append(
                                (pos_name, x_pos, y_pos)  # type: ignore
                            )
                        if c < self.scan_size_c - 1:
                            x_pos += increment_x
                        pos_count += 1

            full_pos_list.extend(list_pos_order)

        return full_pos_list

    def _start_scan(self) -> None:

        self.pixel_size = self._mmc.getPixelSizeUm()

        if len(self._mmc.getLoadedDevices()) < 2:
            raise ValueError("Load a cfg file first.")

        if self.pixel_size <= 0:
            raise ValueError("Pixel Size not set.")

        if self.channel_explorer_tableWidget.rowCount() <= 0:
            raise ValueError("Select at least one channel.")

        explore_sample = self._get_state()

        self._mmc.run_mda(explore_sample)  # run the MDA experiment asynchronously
        return
