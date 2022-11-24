from __future__ import annotations

import warnings
from typing import Optional

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QSize, Qt
from superqt.fonticon import icon
from useq import MDASequence

from .._util import _select_output_unit, _time_in_sec, guess_channel_group
from ._sample_explorer_gui import SampleExplorerGui


class SampleExplorerWidget(SampleExplorerGui):
    """Widget to create and run grid acquisitions.

    The `SampleExplorerWidget` provides a GUI to construct a
    [`useq.MDASequence`](https://github.com/tlambert03/useq-schema) object.
    If the `include_run_button` parameter is set to `True`, a "run" button is added
    to the GUI and, when clicked, the generated
    [`useq.MDASequence`](https://github.com/tlambert03/useq-schema)
    is passed to the
    [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.run_mda]
    method and the acquisition is executed.

    Parameters
    ----------
    parent : Optional[QWidget]
        Optional parent widget, by default None.
    include_run_button: bool
        By default, `False`. If `True`, a "run" button is added to the widget.
        The acquisition defined by the
        [`useq.MDASequence`](https://github.com/tlambert03/useq-schema)
        built through the widget is executed when clicked.
    mmcore: Optional[CMMCorePlus]
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        *,
        parent: QtW.QWidget = None,
        include_run_button: bool = False,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent=parent)

        self._include_run_button = include_run_button

        self.cancel_scan_Button.hide()
        self.pause_scan_Button.hide()
        if not self._include_run_button:
            self.start_scan_Button.hide()

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
        self.go.clicked.connect(self._move_to_position)

        # connect buttons
        if self._include_run_button:
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
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self.pixel_size = self._mmc.getPixelSizeUm()
        if channel_group := self._mmc.getChannelGroup() or guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self._clear_channel()

    def _on_mda_started(self) -> None:
        """Block gui when mda starts."""
        self._set_enabled(False)
        if self._include_run_button:
            self.cancel_scan_Button.show()
            self.pause_scan_Button.show()
        self.start_scan_Button.hide()

    def _on_mda_paused(self, paused: bool) -> None:
        self.pause_scan_Button.setText("Go" if paused else "Pause")

    def _on_mda_finished(self) -> None:

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
        if self._include_run_button:
            self.start_scan_Button.show()

    def _set_enabled(self, enabled: bool) -> None:
        self.scan_size_spinBox_r.setEnabled(enabled)
        self.scan_size_spinBox_c.setEnabled(enabled)
        self.ovelap_spinBox.setEnabled(enabled)
        self.channel_explorer_groupBox.setEnabled(enabled)
        self.time_groupBox.setEnabled(enabled)
        self.acquisition_order_comboBox.setEnabled(enabled)

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
                    item.setWhatsThis(f"Grid_{count:03d}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.stage_tableWidget.setItem(idx, c, item)
                    self._rename_positions()
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue

                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QtW.QTableWidgetItem(str(cur))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
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
        self._rename_positions()
        self._calculate_total_time()

    def _clear_positions(self) -> None:
        # clear all positions
        self.stage_tableWidget.clearContents()
        self.stage_tableWidget.setRowCount(0)
        self._calculate_total_time()

    def _rename_positions(self) -> None:
        for grid_count, r in enumerate(range(self.stage_tableWidget.rowCount())):
            item = self.stage_tableWidget.item(r, 0)
            item_text = item.text()
            item_whatisthis = item.whatsThis()
            if item_text == item_whatisthis:
                new_name = f"Grid_{grid_count:03d}"
            else:
                new_name = item_text
            new_whatisthis = f"Grid_{grid_count:03d}"

            item = QtW.QTableWidgetItem(new_name)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            item.setWhatsThis(new_whatisthis)
            self.stage_tableWidget.setItem(r, 0, item)

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self.stage_tableWidget.currentRow()
        x_val = self.stage_tableWidget.item(curr_row, 1).text()
        y_val = self.stage_tableWidget.item(curr_row, 2).text()
        z_val = self.stage_tableWidget.item(curr_row, 3).text()
        self._mmc.setXYPosition(float(x_val), float(y_val))
        self._mmc.setPosition(self._mmc.getFocusDevice(), float(z_val))

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
                interval = _time_in_sec(interval, int_unit)
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

        min_aq_tp, unit_1 = _select_output_unit(time_chs)

        if interval <= 0:
            effective_interval = 0.0
            addition_time = 0
            _icon = None
            stylesheet = ""

        elif interval < time_chs:
            addition_time = 0
            effective_interval = 0.0
            warning_msg = "Interval shorter than acquisition time per timepoint."
            _icon = icon(MDI6.exclamation_thick, color="magenta").pixmap(QSize(30, 30))
            stylesheet = "color:magenta"

        else:
            effective_interval = float(interval) - time_chs  # s
            addition_time = effective_interval * timepoints  # s
            _icon = None
            stylesheet = ""

        min_tot_time, unit_4 = _select_output_unit(
            (time_chs * timepoints) + addition_time - effective_interval
        )

        self._icon_lbl.clear()
        self._time_lbl.clear()
        self._time_lbl.setStyleSheet(stylesheet)
        if _icon:
            self._icon_lbl.show()
            self._icon_lbl.setPixmap(_icon)
            self._time_lbl.show()
            self._time_lbl.setText(f"{warning_msg}")
            self._time_lbl.adjustSize()
        else:
            self._time_lbl.hide()
            self._icon_lbl.hide()

        t_per_tp_msg = ""
        tot_acq_msg = f"Minimum total acquisition time: {min_tot_time:.4f} {unit_4}.\n"
        if self.time_groupBox.isChecked():
            t_per_tp_msg = (
                f"Minimum acquisition time per timepoint: {min_aq_tp:.4f} {unit_1}."
            )
        self._total_time_lbl.setText(f"{tot_acq_msg}{t_per_tp_msg}")

    def get_state(self) -> MDASequence:  # sourcery skip: merge-dict-assign
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        table = self.channel_explorer_tableWidget

        state = {
            "axis_order": self.acquisition_order_comboBox.currentText(),
            "channels": [],
            "stage_positions": [],
            "z_plan": None,
            "time_plan": None,
        }

        state["channels"] = [
            {
                "config": table.cellWidget(c, 0).currentText(),
                "group": self._mmc.getChannelGroup() or "Channel",
                "exposure": table.cellWidget(c, 1).value(),
            }
            for c in range(table.rowCount())
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

        for g in self._set_grid():
            pos = {"name": g[0], "x": g[1], "y": g[2]}
            if len(g) == 4:
                pos["z"] = g[3]
            state["stage_positions"].append(pos)

        return MDASequence(**state)

    def _get_pos_name(self, row: int) -> str:
        item = self.stage_tableWidget.item(row, 0)
        name = item.text()
        whatsthis = item.whatsThis()
        new_name = f"{name}_{whatsthis}" if whatsthis not in name else name
        return str(new_name)

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
                name = self._get_pos_name(r)
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
        for st_pos in explorer_starting_positions:
            name, x_pos, y_pos = st_pos[0], st_pos[1], st_pos[2]  # type: ignore
            if self._mmc.getFocusDevice():
                z_pos = st_pos[3]

            self.return_to_position_x = x_pos  # type: ignore
            self.return_to_position_y = y_pos  # type: ignore

            # calculate initial scan position
            _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())

            overlap_percentage = self.ovelap_spinBox.value()
            overlap_px_w = width - (width * overlap_percentage) / 100
            overlap_px_h = height - (height * overlap_percentage) / 100

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

        return full_pos_list  # type: ignore

    def _start_scan(self) -> None:

        self.pixel_size = self._mmc.getPixelSizeUm()

        if self._mmc.getPixelSizeUm() <= 0:
            # raise ValueError("Pixel Size not set.")
            warnings.warn("Pixel Size not set.")
            return

        # construct a `useq.MDASequence` object from the values inserted in the widget
        explore_sample = self.get_state()
        # run the MDA experiment asynchronously
        self._mmc.run_mda(explore_sample)
        return
