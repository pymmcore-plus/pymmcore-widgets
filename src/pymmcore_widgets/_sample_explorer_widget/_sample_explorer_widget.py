from __future__ import annotations

import warnings

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from useq import MDASequence

from .._util import _select_output_unit, guess_channel_group
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
        parent: QtW.QWidget = None,
        include_run_button: bool = False,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._include_run_button = include_run_button

        self.buttons_wdg.cancel_button.hide()
        self.buttons_wdg.pause_button.hide()
        if not self._include_run_button:
            self.buttons_wdg.run_button.hide()

        self.buttons_wdg.pause_button.released.connect(self._mmc.mda.toggle_pause)
        self.buttons_wdg.cancel_button.released.connect(self._mmc.mda.cancel)

        self.pixel_size = self._mmc.getPixelSizeUm()

        self.return_to_position_x = None
        self.return_to_position_y = None

        # connect valueUpdated signal
        self.channel_groupbox.valueUpdated.connect(self._update_total_time)
        self.stack_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.toggled.connect(self._update_total_time)

        # connect run button
        if self._include_run_button:
            self.buttons_wdg.run_button.clicked.connect(self._start_scan)

        # connection for positions
        self.stage_pos_groupbox.add_pos_button.clicked.connect(self._add_position)
        self.stage_pos_groupbox.remove_pos_button.clicked.connect(self._remove_position)
        self.stage_pos_groupbox.clear_pos_button.clicked.connect(self._clear_positions)
        self.stage_pos_groupbox.toggled.connect(self._update_total_time)

        # connection for scan size
        self.scan_size_spinBox_r.valueChanged.connect(self._update_total_time)
        self.scan_size_spinBox_c.valueChanged.connect(self._update_total_time)

        # connect mmcore signals
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self.pixel_size = self._mmc.getPixelSizeUm()
        if channel_group := self._mmc.getChannelGroup() or guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self.channel_groupbox._clear_channel()
        self._clear_positions()

    def _set_enabled(self, enabled: bool) -> None:
        self.scan_size_spinBox_r.setEnabled(enabled)
        self.scan_size_spinBox_c.setEnabled(enabled)
        self.ovelap_spinBox.setEnabled(enabled)
        self.channel_groupbox.setEnabled(enabled)
        self.time_groupbox.setEnabled(enabled)
        self.buttons_wdg.acquisition_order_comboBox.setEnabled(enabled)

        if not self._mmc.getXYStageDevice():
            self.stage_pos_groupbox.setChecked(False)
            self.stage_pos_groupbox.setEnabled(False)
        else:
            self.stage_pos_groupbox.setEnabled(enabled)

        if not self._mmc.getFocusDevice():
            self.stack_groupbox.setChecked(False)
            self.stack_groupbox.setEnabled(False)
        else:
            self.stack_groupbox.setEnabled(enabled)

    # add, remove, clear, move_to positions table
    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("GXYZ"):
                if ax == "G":
                    count = self.stage_pos_groupbox.stage_tableWidget.rowCount()
                    item = QtW.QTableWidgetItem(f"Grid_{count:03d}")
                    item.setWhatsThis(f"Grid_{count:03d}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.stage_pos_groupbox.stage_tableWidget.setItem(idx, c, item)
                    self._rename_positions()
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue

                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QtW.QTableWidgetItem(str(cur))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.stage_pos_groupbox.stage_tableWidget.setItem(idx, c, item)

        self._update_total_time()

    def _add_position_row(self) -> int:
        idx = int(self.stage_pos_groupbox.stage_tableWidget.rowCount())
        self.stage_pos_groupbox.stage_tableWidget.insertRow(idx)
        return idx

    def _remove_position(self) -> None:
        # remove selected position
        rows = {
            r.row() for r in self.stage_pos_groupbox.stage_tableWidget.selectedIndexes()
        }
        for idx in sorted(rows, reverse=True):
            self.stage_pos_groupbox.stage_tableWidget.removeRow(idx)
        self._rename_positions()
        self._update_total_time()

    def _clear_positions(self) -> None:
        # clear all positions
        self.stage_pos_groupbox.stage_tableWidget.clearContents()
        self.stage_pos_groupbox.stage_tableWidget.setRowCount(0)
        self._update_total_time()

    def _rename_positions(self) -> None:
        for grid_count, r in enumerate(
            range(self.stage_pos_groupbox.stage_tableWidget.rowCount())
        ):
            item = self.stage_pos_groupbox.stage_tableWidget.item(r, 0)
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
            self.stage_pos_groupbox.stage_tableWidget.setItem(r, 0, item)

    def _get_pos_name(self, row: int) -> str:
        item = self.stage_pos_groupbox.stage_tableWidget.item(row, 0)
        name = item.text()
        whatsthis = item.whatsThis()
        new_name = f"{name}_{whatsthis}" if whatsthis not in name else name
        return str(new_name)

    def _set_grid(self) -> list[tuple[str, float, float, float | None]]:

        self.scan_size_r = self.scan_size_spinBox_r.value()
        self.scan_size_c = self.scan_size_spinBox_c.value()
        self.pixel_size = self._mmc.getPixelSizeUm()

        explorer_starting_positions = []
        if (
            self.stage_pos_groupbox.isChecked()
            and self.stage_pos_groupbox.stage_tableWidget.rowCount() > 0
        ):
            for r in range(self.stage_pos_groupbox.stage_tableWidget.rowCount()):
                name = self._get_pos_name(r)
                x = float(self.stage_pos_groupbox.stage_tableWidget.item(r, 1).text())
                y = float(self.stage_pos_groupbox.stage_tableWidget.item(r, 2).text())
                z = float(self.stage_pos_groupbox.stage_tableWidget.item(r, 3).text())
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

    def _update_total_time(self) -> None:

        tiles = self.scan_size_spinBox_r.value() * self.scan_size_spinBox_c.value()

        # channel
        exp: list = []
        ch = self.channel_groupbox.channel_tableWidget.rowCount()
        if ch > 0:
            exp.extend(
                self.channel_groupbox.channel_tableWidget.cellWidget(r, 1).value()
                for r in range(ch)
            )
        else:
            exp = []

        # time
        if self.time_groupbox.isChecked():
            val = self.time_groupbox.value()
            timepoints = val["loops"]
            interval = val["interval"].total_seconds()
        else:
            timepoints = 1
            interval = -1.0

        # z stack
        n_z_images = (
            self.stack_groupbox.n_images() if self.stack_groupbox.isChecked() else 1
        )

        # positions
        if self.stage_pos_groupbox.isChecked():
            n_pos = self.stage_pos_groupbox.stage_tableWidget.rowCount() or 1
        else:
            n_pos = 1
        n_pos = n_pos

        # acq time per timepoint
        time_chs: float = 0.0  # s
        for e in exp:
            time_chs = time_chs + ((e / 1000) * n_z_images * n_pos * tiles)

        min_aq_tp, unit_1 = _select_output_unit(time_chs)

        addition_time = 0.0
        effective_interval = 0.0
        if interval >= time_chs:
            effective_interval = float(interval) - time_chs  # s
            addition_time = effective_interval * timepoints  # s

        min_tot_time, unit_4 = _select_output_unit(
            (time_chs * timepoints) + addition_time - effective_interval
        )

        self.time_groupbox.setWarningVisible(-1 < interval < time_chs)

        t_per_tp_msg = ""
        tot_acq_msg = f"Minimum total acquisition time: {min_tot_time:.4f} {unit_4}.\n"
        if self.time_groupbox.isChecked():
            t_per_tp_msg = (
                f"Minimum acquisition time per timepoint: {min_aq_tp:.4f} {unit_1}."
            )
        self.time_lbl._total_time_lbl.setText(f"{tot_acq_msg}{t_per_tp_msg}")

    def _on_mda_started(self) -> None:
        """Block gui when mda starts."""
        self._set_enabled(False)
        if self._include_run_button:
            self.buttons_wdg.cancel_button.show()
            self.buttons_wdg.pause_button.show()
        self.buttons_wdg.run_button.hide()

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
        self.buttons_wdg.cancel_button.hide()
        self.buttons_wdg.pause_button.hide()
        if self._include_run_button:
            self.buttons_wdg.run_button.show()

    def _on_mda_paused(self, paused: bool) -> None:
        self.buttons_wdg.pause_button.setText("Go" if paused else "Pause")

    def get_state(self) -> MDASequence:  # sourcery skip: merge-dict-assign
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        table = self.channel_groupbox.channel_tableWidget

        channels: list[dict] = [
            {
                "config": table.cellWidget(c, 0).currentText(),
                "group": self._mmc.getChannelGroup() or "Channel",
                "exposure": table.cellWidget(c, 1).value(),
            }
            for c in range(table.rowCount())
        ]

        z_plan = (
            self.stack_groupbox.value() if self.stack_groupbox.isChecked() else None
        )
        time_plan = (
            self.time_groupbox.value() if self.time_groupbox.isChecked() else None
        )

        stage_positions: list[dict] = []
        for g in self._set_grid():
            pos = {"name": g[0], "x": g[1], "y": g[2]}
            if len(g) == 4:
                pos["z"] = g[3]
            stage_positions.append(pos)

        return MDASequence(
            axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText(),
            channels=channels,
            stage_positions=stage_positions,
            z_plan=z_plan,
            time_plan=time_plan,
        )

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
