from __future__ import annotations

from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from useq import MDASequence

from .._util import _select_output_unit, guess_channel_group
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

        # connect valueUpdated signal
        self.channel_groupbox.valueChanged.connect(self._update_total_time)
        self.stack_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.toggled.connect(self._update_total_time)

        # connect run button
        if self._include_run_button:
            self.buttons_wdg.run_button.clicked.connect(self._on_run_clicked)

        # connection for positions
        self.stage_pos_groupbox.add_pos_button.clicked.connect(self._add_position)
        self.stage_pos_groupbox.remove_pos_button.clicked.connect(self._remove_position)
        self.stage_pos_groupbox.clear_pos_button.clicked.connect(self._clear_positions)
        self.stage_pos_groupbox.grid_button.clicked.connect(self._grid_widget)
        self.stage_pos_groupbox.toggled.connect(self._update_total_time)

        # connect mmcore signals
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        if channel_group := self._mmc.getChannelGroup() or guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self.channel_groupbox.clear()
        self._clear_positions()

    def _set_enabled(self, enabled: bool) -> None:
        self.time_groupbox.setEnabled(enabled)
        self.buttons_wdg.acquisition_order_comboBox.setEnabled(enabled)
        self.channel_groupbox.setEnabled(enabled)

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

            for c, ax in enumerate("PXYZ"):

                if ax == "P":
                    count = self.stage_pos_groupbox.stage_tableWidget.rowCount() - 1
                    item = QtW.QTableWidgetItem(f"Pos{count:03d}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.stage_pos_groupbox.stage_tableWidget.setItem(idx, c, item)
                    self._rename_positions(["Pos"])
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
        idx = self.stage_pos_groupbox.stage_tableWidget.rowCount()
        self.stage_pos_groupbox.stage_tableWidget.insertRow(idx)
        return idx  # type: ignore [no-any-return]

    def _remove_position(self) -> None:
        # remove selected position
        rows = {
            r.row() for r in self.stage_pos_groupbox.stage_tableWidget.selectedIndexes()
        }
        removed = []
        for idx in sorted(rows, reverse=True):
            name = (
                self.stage_pos_groupbox.stage_tableWidget.item(idx, 0)
                .text()
                .split("_")[0]
            )
            if "Pos" in name:
                if "Pos" not in removed:
                    removed.append("Pos")
            elif name not in removed:
                removed.append(name)
            self.stage_pos_groupbox.stage_tableWidget.removeRow(idx)
        self._rename_positions(removed)
        self._update_total_time()

    def _rename_positions(self, names: list) -> None:
        for name in names:
            grid_count = 0
            pos_count = 0
            for r in range(self.stage_pos_groupbox.stage_tableWidget.rowCount()):
                start = (
                    self.stage_pos_groupbox.stage_tableWidget.item(r, 0)
                    .text()
                    .split("_")[0]
                )
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
                self.stage_pos_groupbox.stage_tableWidget.setItem(r, 0, item)

    def _clear_positions(self) -> None:
        # clear all positions
        self.stage_pos_groupbox.stage_tableWidget.clearContents()
        self.stage_pos_groupbox.stage_tableWidget.setRowCount(0)
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
            for r in range(self.stage_pos_groupbox.stage_tableWidget.rowCount()):
                pos_name = self.stage_pos_groupbox.stage_tableWidget.item(r, 0).text()
                grid_name = pos_name.split("_")[0]
                if "Grid" in grid_name:
                    grid_n = grid_name[-3:]
                    if int(grid_n) > grid_number:
                        grid_number = int(grid_n)
            grid_number += 1

        for idx, position in enumerate(position_list):
            rows = self.stage_pos_groupbox.stage_tableWidget.rowCount()
            self.stage_pos_groupbox.stage_tableWidget.insertRow(rows)

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

            self.stage_pos_groupbox.stage_tableWidget.setItem(rows, 0, item)
            self.stage_pos_groupbox.stage_tableWidget.setItem(rows, 1, x)
            self.stage_pos_groupbox.stage_tableWidget.setItem(rows, 2, y)
            self.stage_pos_groupbox.stage_tableWidget.setItem(rows, 3, z)

    def _update_total_time(self) -> None:
        # channel
        exp: list[float] = [
            e for c in self.channel_groupbox.value() if (e := c.get("exposure"))
        ]

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
            time_chs = time_chs + ((e / 1000) * n_z_images * n_pos)

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
        # sourcery skip: low-code-quality
        if isinstance(state, (str, Path)):
            state = MDASequence.parse_file(state)
        elif isinstance(state, dict):
            state = MDASequence(**state)
        if not isinstance(state, MDASequence):
            raise TypeError("state must be an MDASequence, dict, or yaml file")

        self.buttons_wdg.acquisition_order_comboBox.setCurrentText(state.axis_order)

        # set channel table
        if state.channels:
            self.channel_groupbox.set_state([c.dict() for c in state.channels])

        # set Z
        if state.z_plan:
            self.stack_groupbox.setChecked(True)
            self.stack_groupbox.set_state(state.z_plan.dict())
        else:
            self.stack_groupbox.setChecked(False)

        # set time
        if state.time_plan:
            self.time_groupbox.setChecked(True)
            self.time_groupbox.set_state(state.time_plan.dict())
        else:
            self.time_groupbox.setChecked(False)

        # set stage positions
        self._clear_positions()
        if state.stage_positions:
            self.stage_pos_groupbox.setChecked(True)
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
                    self.stage_pos_groupbox.stage_tableWidget.setItem(idx, c, item)
        else:
            self.stage_pos_groupbox.setChecked(False)

    def get_state(self) -> MDASequence:
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        channels = self.channel_groupbox.value()

        z_plan = (
            self.stack_groupbox.value() if self.stack_groupbox.isChecked() else None
        )
        time_plan = (
            self.time_groupbox.value() if self.time_groupbox.isChecked() else None
        )

        # position settings
        stage_positions: list = []

        if self._mmc.getXYStageDevice():
            if (
                self.stage_pos_groupbox.isChecked()
                and self.stage_pos_groupbox.stage_tableWidget.rowCount() > 0
            ):
                for r in range(self.stage_pos_groupbox.stage_tableWidget.rowCount()):
                    pos = {
                        "name": self.stage_pos_groupbox.stage_tableWidget.item(
                            r, 0
                        ).text(),
                        "x": float(
                            self.stage_pos_groupbox.stage_tableWidget.item(r, 1).text()
                        ),
                        "y": float(
                            self.stage_pos_groupbox.stage_tableWidget.item(r, 2).text()
                        ),
                    }
                    if self._mmc.getFocusDevice():
                        pos["z"] = float(
                            self.stage_pos_groupbox.stage_tableWidget.item(r, 3).text()
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
