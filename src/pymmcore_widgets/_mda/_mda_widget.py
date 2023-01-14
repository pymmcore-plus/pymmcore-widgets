from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from useq import MDASequence

from .._util import _select_output_unit, guess_channel_group
from ._channel_table_widget import ChannelTable
from ._general_mda_widgets import _MDAControlButtons, _MDATimeLabel
from ._positions_table_widget import PositionTable
from ._time_plan_widget import TimePlanWidget
from ._zstack_widget import ZStackWidget

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class PositionDict(TypedDict, total=False):
        """Position dictionary."""

        x: float | None
        y: float | None
        z: float | None
        name: str | None


LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class MDAWidget(QWidget):
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

        # Widgets for Channels, Time, ZStack, and Positions in the Scroll Area
        self.channel_groupbox = ChannelTable()
        self.channel_groupbox.valueChanged.connect(self._enable_run_btn)

        self.time_groupbox = TimePlanWidget()
        self.time_groupbox.setChecked(False)

        self.stack_groupbox = ZStackWidget()
        self.stack_groupbox.setChecked(False)

        self.position_groupbox = PositionTable()
        self.position_groupbox.setChecked(False)

        # below the scroll area, some feedback widgets and buttons
        self.time_lbl = _MDATimeLabel()

        self.buttons_wdg = _MDAControlButtons()
        self.buttons_wdg.pause_button.hide()
        self.buttons_wdg.cancel_button.hide()
        self.buttons_wdg.run_button.hide()

        # LAYOUT

        central_layout = QVBoxLayout()
        central_layout.setSpacing(20)
        central_layout.setContentsMargins(10, 10, 10, 10)
        central_layout.addWidget(self.channel_groupbox)
        central_layout.addWidget(self.time_groupbox)
        central_layout.addWidget(self.stack_groupbox)
        central_layout.addWidget(self.position_groupbox)
        self._central_widget = QWidget()
        self._central_widget.setLayout(central_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(self._central_widget)

        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(10)
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().addWidget(scroll)
        self.layout().addWidget(self.time_lbl)
        self.layout().addWidget(self.buttons_wdg)

        # CONNECTIONS

        self.buttons_wdg.pause_button.released.connect(self._mmc.mda.toggle_pause)
        self.buttons_wdg.cancel_button.released.connect(self._mmc.mda.cancel)
        # connect valueUpdated signal
        self.channel_groupbox.valueChanged.connect(self._update_total_time)
        self.stack_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.toggled.connect(self._update_total_time)
        self.position_groupbox.valueChanged.connect(self._update_total_time)
        # connect mmcore signals
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        # connect run button
        if self._include_run_button:
            self.buttons_wdg.run_button.clicked.connect(self._on_run_clicked)
            self.buttons_wdg.run_button.show()

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        if channel_group := self._mmc.getChannelGroup() or guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self.channel_groupbox.clear()

    def _set_enabled(self, enabled: bool) -> None:
        self.time_groupbox.setEnabled(enabled)
        self.buttons_wdg.acquisition_order_comboBox.setEnabled(enabled)
        self.channel_groupbox.setEnabled(enabled)

        if not self._mmc.getXYStageDevice():
            self.position_groupbox.setChecked(False)
            self.position_groupbox.setEnabled(False)
        else:
            self.position_groupbox.setEnabled(enabled)

        if not self._mmc.getFocusDevice():
            self.stack_groupbox.setChecked(False)
            self.stack_groupbox.setEnabled(False)
        else:
            self.stack_groupbox.setEnabled(enabled)

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
        if state.stage_positions:
            self.position_groupbox.set_state([p.dict() for p in state.stage_positions])
        else:
            self.position_groupbox.setChecked(False)

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

        stage_positions = (
            self.position_groupbox.value()
            if self.position_groupbox.isChecked()
            else self._get_current_position()
        )

        return MDASequence(
            axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText(),
            channels=channels,
            stage_positions=stage_positions,
            z_plan=z_plan,
            time_plan=time_plan,
        )

    def _get_current_position(self) -> list[PositionDict]:
        return [
            {
                "name": "Pos000",
                "x": (
                    self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
                ),
                "y": (
                    self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
                ),
                "z": (self._mmc.getZPosition() if self._mmc.getFocusDevice() else None),
            }
        ]

    def _on_run_clicked(self) -> None:
        """Run the MDA sequence experiment."""
        # construct a `useq.MDASequence` object from the values inserted in the widget
        experiment = self.get_state()
        # run the MDA experiment asynchronously
        self._mmc.run_mda(experiment)
        return

    def _enable_run_btn(self) -> None:
        self.buttons_wdg.run_button.setEnabled(
            self.channel_groupbox._table.rowCount() > 0
        )

    def _update_total_time(self, *, tiles: int = 1) -> None:
        """Update the minimum total acquisition time info."""
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
        if self.position_groupbox.isChecked():
            n_pos = len(self.position_groupbox.value()) or 1
        else:
            n_pos = 1

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

        self.time_groupbox.setWarningVisible(0 < interval < time_chs)

        t_per_tp_msg = ""
        tot_acq_msg = f"Minimum total acquisition time: {min_tot_time:.4f} {unit_4}.\n"
        if self.time_groupbox.isChecked():
            t_per_tp_msg = (
                f"Minimum acquisition time per timepoint: {min_aq_tp:.4f} {unit_1}."
            )
        self.time_lbl._total_time_lbl.setText(f"{tot_acq_msg}{t_per_tp_msg}")
