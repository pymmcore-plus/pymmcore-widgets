from __future__ import annotations

import warnings
from pathlib import Path

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QSize, Qt
from superqt.fonticon import icon
from useq import MDASequence

from .._util import _select_output_unit, _time_in_sec, guess_channel_group
from ._grid_widget import GridWidget
from ._mda_gui import _MDAWidgetGui


class MDAWidget(_MDAWidgetGui):
    """A Multi-dimensional acquisition Widget.

    The `MDAWidget` provides a GUI to construct a
    [`useq.MDASequence`](https://github.com/tlambert03/useq-schema) object.
    If the `include_run_button` parameter is set to `True`, a "run" button is added
    to the GUI and, when clicked, the generated
    [`useq.MDASequence`](https://github.com/tlambert03/useq-schema)
    is passed to the
    [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.run_mda]
    method and the acquisition
    is executed.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    include_run_button: bool
        By default, `False`. If `True`, a "run" button is added to the widget.
        The acquisition defined by the
        [`useq.MDASequence`](https://github.com/tlambert03/useq-schema)
        built through the widget is executed when clicked.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        *,
        parent: QtW.QWidget | None = None,
        include_run_button: bool = False,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._include_run_button = include_run_button

        self.buttons_wdg.pause_button.hide()
        self.buttons_wdg.cancel_button.hide()
        if not self._include_run_button:
            self.buttons_wdg.run_button.hide()

        self.buttons_wdg.pause_button.released.connect(self._mmc.mda.toggle_pause)
        self.buttons_wdg.cancel_button.released.connect(self._mmc.mda.cancel)

        self.ch_gb = self.channel_groupbox
        self.tm_gp = self.time_groupbox
        self.z_gp = self.stack_groupbox
        self.pos_gp = self.stage_pos_groupbox

        # connect valueUpdated signal
        self.ch_gb.valueUpdated.connect(self._update_total_time)
        self.z_gp.valueChanged.connect(self._update_total_time)
        self.tm_gp.valueUpdated.connect(self._update_total_time)

        # connect run button
        if self._include_run_button:
            self.buttons_wdg.run_button.clicked.connect(self._on_run_clicked)

        # connection for positions
        self.pos_gp.add_pos_button.clicked.connect(self._add_position)
        self.pos_gp.remove_pos_button.clicked.connect(self._remove_position)
        self.pos_gp.clear_pos_button.clicked.connect(self._clear_positions)
        self.pos_gp.grid_button.clicked.connect(self._grid_widget)
        self.pos_gp.toggled.connect(self._update_total_time)

        # connect mmcore signals
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        if channel_group := self._mmc.getChannelGroup() or guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self.ch_gb._clear_channel()
        self._clear_positions()

    def _set_enabled(self, enabled: bool) -> None:
        self.tm_gp.setEnabled(enabled)
        self.buttons_wdg.acquisition_order_comboBox.setEnabled(enabled)
        self.ch_gb.setEnabled(enabled)

        if not self._mmc.getXYStageDevice():
            self.pos_gp.setChecked(False)
            self.pos_gp.setEnabled(False)
        else:
            self.pos_gp.setEnabled(enabled)

        if not self._mmc.getFocusDevice():
            self.z_gp.setChecked(False)
            self.z_gp.setEnabled(False)
        else:
            self.z_gp.setEnabled(enabled)

    # add, remove, clear, move_to positions table
    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("PXYZ"):

                if ax == "P":
                    count = self.pos_gp.stage_tableWidget.rowCount() - 1
                    item = QtW.QTableWidgetItem(f"Pos{count:03d}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.pos_gp.stage_tableWidget.setItem(idx, c, item)
                    self._rename_positions(["Pos"])
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue
                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QtW.QTableWidgetItem(str(cur))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.pos_gp.stage_tableWidget.setItem(idx, c, item)

            self._update_total_time()

    def _add_position_row(self) -> int:
        idx = self.pos_gp.stage_tableWidget.rowCount()
        self.pos_gp.stage_tableWidget.insertRow(idx)
        return idx  # type: ignore [no-any-return]

    def _remove_position(self) -> None:
        # remove selected position
        rows = {r.row() for r in self.pos_gp.stage_tableWidget.selectedIndexes()}
        removed = []
        for idx in sorted(rows, reverse=True):
            name = self.pos_gp.stage_tableWidget.item(idx, 0).text().split("_")[0]
            if "Pos" in name:
                if "Pos" not in removed:
                    removed.append("Pos")
            elif name not in removed:
                removed.append(name)
            self.pos_gp.stage_tableWidget.removeRow(idx)
        self._rename_positions(removed)
        self._update_total_time()

    def _rename_positions(self, names: list) -> None:
        for name in names:
            grid_count = 0
            pos_count = 0
            for r in range(self.pos_gp.stage_tableWidget.rowCount()):
                start = self.pos_gp.stage_tableWidget.item(r, 0).text().split("_")[0]
                if start == name:  # Grid
                    new_name = f"{name}_Pos{grid_count:03d}"
                    grid_count += 1
                elif "Pos" in start:  # Pos
                    new_name = f"Pos{pos_count:03d}"
                    pos_count += 1
                else:
                    continue
                item = QtW.QTableWidgetItem(new_name)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.pos_gp.stage_tableWidget.setItem(r, 0, item)

    def _clear_positions(self) -> None:
        # clear all positions
        self.pos_gp.stage_tableWidget.clearContents()
        self.pos_gp.stage_tableWidget.setRowCount(0)
        self._update_total_time()

    def _grid_widget(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        if not hasattr(self, "_grid_wdg"):
            self._grid_wdg = GridWidget(parent=self)
            self._grid_wdg.sendPosList.connect(self._add_to_position_table)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_to_position_table(self, position_list: list, clear: bool) -> None:

        grid_number = 0

        if clear:
            self._clear_positions()
        else:
            for r in range(self.pos_gp.stage_tableWidget.rowCount()):
                pos_name = self.pos_gp.stage_tableWidget.item(r, 0).text()
                grid_name = pos_name.split("_")[0]
                if "Grid" in grid_name:
                    grid_n = grid_name[-3:]
                    if int(grid_n) > grid_number:
                        grid_number = int(grid_n)
            grid_number += 1

        for idx, position in enumerate(position_list):
            rows = self.pos_gp.stage_tableWidget.rowCount()
            self.pos_gp.stage_tableWidget.insertRow(rows)

            item = QtW.QTableWidgetItem(f"Grid{grid_number:03d}_Pos{idx:03d}")
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            x = QtW.QTableWidgetItem(str(position[0]))
            x.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            y = QtW.QTableWidgetItem(str(position[1]))
            y.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            z = QtW.QTableWidgetItem(str(position[2]))
            z.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )

            self.pos_gp.stage_tableWidget.setItem(rows, 0, item)
            self.pos_gp.stage_tableWidget.setItem(rows, 1, x)
            self.pos_gp.stage_tableWidget.setItem(rows, 2, y)
            self.pos_gp.stage_tableWidget.setItem(rows, 3, z)

    def _update_total_time(self) -> None:

        # channel
        exp: list = []
        ch = self.ch_gb.channel_tableWidget.rowCount()
        if ch > 0:
            exp.extend(
                self.ch_gb.channel_tableWidget.cellWidget(r, 1).value()
                for r in range(ch)
            )
        else:
            exp = []

        # time
        if self.tm_gp.isChecked():
            timepoints = self.tm_gp.timepoints_spinBox.value()
            interval = self.tm_gp.interval_spinBox.value()
            int_unit = self.tm_gp.time_comboBox.currentText()
            if int_unit != "sec":
                interval = _time_in_sec(interval, int_unit)
        else:
            timepoints = 1
            interval = -1.0

        # z stack
        n_z_images = self.z_gp.n_images() if self.z_gp.isChecked() else 1

        # positions
        if self.pos_gp.isChecked():
            n_pos = self.pos_gp.stage_tableWidget.rowCount() or 1
        else:
            n_pos = 1
        n_pos = n_pos

        # acq time per timepoint
        time_chs: float = 0.0  # s
        for e in exp:
            time_chs = time_chs + ((e / 1000) * n_z_images * n_pos)

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

        self.tm_gp._icon_lbl.clear()
        self.tm_gp._time_lbl.clear()
        self.tm_gp._time_lbl.setStyleSheet(stylesheet)
        if _icon:
            self.tm_gp._icon_lbl.show()
            self.tm_gp._icon_lbl.setPixmap(_icon)
            self.tm_gp._time_lbl.show()
            self.tm_gp._time_lbl.setText(f"{warning_msg}")
            self.tm_gp._time_lbl.adjustSize()
        else:
            self.tm_gp._time_lbl.hide()
            self.tm_gp._icon_lbl.hide()

        t_per_tp_msg = ""
        tot_acq_msg = f"Minimum total acquisition time: {min_tot_time:.4f} {unit_4}.\n"
        if self.tm_gp.isChecked():
            t_per_tp_msg = (
                f"Minimum acquisition time per timepoint: {min_aq_tp:.4f} {unit_1}."
            )
        self.time_lbl._total_time_lbl.setText(f"{tot_acq_msg}{t_per_tp_msg}")

    def _on_mda_started(self) -> None:
        self._set_enabled(False)
        if self._include_run_button:
            self.buttons_wdg.pause_button.show()
            self.buttons_wdg.cancel_button.show()
        self.buttons_wdg.run_button.hide()

    def _on_mda_finished(self) -> None:
        self._set_enabled(True)
        self.buttons_wdg.pause_button.hide()
        self.buttons_wdg.cancel_button.hide()
        if self._include_run_button:
            self.buttons_wdg.run_button.show()

    def _on_mda_paused(self, paused: bool) -> None:
        self.buttons_wdg.pause_button.setText("Resume" if paused else "Pause")

    def set_state(self, state: dict | MDASequence | str | Path) -> None:
        """Set current state of MDA widget.

        Parameters
        ----------
        state : dict | MDASequence | str | Path
            MDASequence state in the form of a dict, MDASequence object, or a str or
            Path pointing to a sequence.yaml file
        """
        if isinstance(state, (str, Path)):
            state = MDASequence.parse_file(state)
        elif isinstance(state, dict):
            state = MDASequence(**state)
        if not isinstance(state, MDASequence):
            raise TypeError("state must be an MDASequence, dict, or yaml file")

        self.buttons_wdg.acquisition_order_comboBox.setCurrentText(state.axis_order)

        # set channel table
        self.ch_gb._clear_channel()
        if channel_group := self._mmc.getChannelGroup():
            channel_list = list(self._mmc.getAvailableConfigs(channel_group))
        else:
            channel_list = []
        for idx, ch in enumerate(state.channels):
            if not self.ch_gb._add_channel():
                break
            if ch.config in channel_list:
                self.ch_gb.channel_tableWidget.cellWidget(idx, 0).setCurrentText(
                    ch.config
                )
            else:
                warnings.warn(
                    f"Unrecognized channel: {ch.config!r}. "
                    f"Valid channels include {channel_list}"
                )
            if ch.exposure:
                self.ch_gb.channel_tableWidget.cellWidget(idx, 1).setValue(
                    int(ch.exposure)
                )

        # set Z
        if state.z_plan:
            self.z_gp.setChecked(True)
            self.z_gp.set_state(state.z_plan.dict())
        else:
            self.z_gp.setChecked(False)

        # set time
        # currently only `TIntervalLoops` is supported
        if hasattr(state.time_plan, "interval") and hasattr(state.time_plan, "loops"):
            self.tm_gp.setChecked(True)
            self.tm_gp.timepoints_spinBox.setValue(state.time_plan.loops)

            sec = state.time_plan.interval.total_seconds()
            if sec >= 60:
                self.tm_gp.time_comboBox.setCurrentText("min")
                self.tm_gp.interval_spinBox.setValue(sec // 60)
            elif sec >= 1:
                self.tm_gp.time_comboBox.setCurrentText("sec")
                self.tm_gp.interval_spinBox.setValue(int(sec))
            else:
                self.tm_gp.time_comboBox.setCurrentText("ms")
                self.tm_gp.interval_spinBox.setValue(int(sec * 1000))
        else:
            self.tm_gp.setChecked(False)

        # set stage positions
        self._clear_positions()
        if state.stage_positions:
            self.pos_gp.setChecked(True)
            for idx, pos in enumerate(state.stage_positions):
                self._add_position_row()
                for c, ax in enumerate("pxyz"):
                    if ax == "p":
                        pos_name = pos.name or f"Pos{idx:03d}"
                        item = QtW.QTableWidgetItem(str(pos_name))
                    else:
                        item = QtW.QTableWidgetItem(str(getattr(pos, ax)))
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.pos_gp.stage_tableWidget.setItem(idx, c, item)
        else:
            self.pos_gp.setChecked(False)

    def get_state(self) -> MDASequence:
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        channels: list[dict] = [
            {
                "config": self.ch_gb.channel_tableWidget.cellWidget(c, 0).currentText(),
                "group": self._mmc.getChannelGroup() or "Channel",
                "exposure": self.ch_gb.channel_tableWidget.cellWidget(c, 1).value(),
            }
            for c in range(self.ch_gb.channel_tableWidget.rowCount())
        ]

        z_plan = self.z_gp.value() if self.z_gp.isChecked() else None

        time_plan: dict | None = None
        if self.tm_gp.isChecked():
            unit = {"min": "minutes", "sec": "seconds", "ms": "milliseconds"}[
                self.tm_gp.time_comboBox.currentText()
            ]
            time_plan = {
                "interval": {unit: self.tm_gp.interval_spinBox.value()},
                "loops": self.tm_gp.timepoints_spinBox.value(),
            }

        # position settings
        stage_positions: list = []

        if self._mmc.getXYStageDevice():
            if self.pos_gp.isChecked() and self.pos_gp.stage_tableWidget.rowCount() > 0:
                for r in range(self.pos_gp.stage_tableWidget.rowCount()):
                    pos = {
                        "name": self.pos_gp.stage_tableWidget.item(r, 0).text(),
                        "x": float(self.pos_gp.stage_tableWidget.item(r, 1).text()),
                        "y": float(self.pos_gp.stage_tableWidget.item(r, 2).text()),
                    }
                    if self._mmc.getFocusDevice():
                        pos["z"] = float(
                            self.pos_gp.stage_tableWidget.item(r, 3).text()
                        )
                    stage_positions.append(pos)
            else:
                pos = {
                    "name": "Pos_000",
                    "x": float(self._mmc.getXPosition()),
                    "y": float(self._mmc.getYPosition()),
                }
                if self._mmc.getFocusDevice():
                    pos["z"] = float(self._mmc.getZPosition())
                stage_positions.append(pos)

        return MDASequence(
            axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText(),
            channels=channels,
            stage_positions=stage_positions,
            z_plan=z_plan,
            time_plan=time_plan,
        )

    def _on_run_clicked(self) -> None:
        """Run the MDA sequence experiment."""
        # construct a `useq.MDASequence` object from the values inserted in the widget
        experiment = self.get_state()
        # run the MDA experiment asynchronously
        self._mmc.run_mda(experiment)  # run the MDA experiment asynchronously
        return
