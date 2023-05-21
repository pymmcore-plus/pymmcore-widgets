from __future__ import annotations

import warnings
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QScrollArea,
    QSizePolicy,
    QTabBar,
    QVBoxLayout,
    QWidget,
)
from useq import MDASequence, NoGrid, NoT, NoZ

from .._util import fmt_timedelta, guess_channel_group
from ._channel_table_widget import ChannelTable
from ._checkable_tabwidget_widget import CheckableTabWidget
from ._general_mda_widgets import _MDAControlButtons, _MDATimeLabel
from ._grid_widget import GridWidget
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
        sequence: MDASequence | None


LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class TabBar(QTabBar):
    """A TabBar subclass that allows to control the minimum width of each tab."""

    def __init__(self, parent: QWidget | None = None, *, checkbox_width: int = 0):
        super().__init__(parent)

        self._checkbox_width = checkbox_width

    def tabSizeHint(self, index: int) -> QSize:
        size = QTabBar.tabSizeHint(self, index)
        w = int(size.width() + self._checkbox_width)
        return QSize(w, size.height())


class Grid(GridWidget):
    """Sunclass GridWidget to emit valueChanged when grid is changed."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.layout().itemAt(2).widget().hide()

    def _update_info(self) -> None:
        super()._update_info()
        self.valueChanged.emit(self.value())


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

        # LAYOUT
        central_layout = QVBoxLayout()
        central_layout.setSpacing(20)
        central_layout.setContentsMargins(10, 10, 10, 10)

        # main TabWidget
        self._tab = CheckableTabWidget(change_tab_on_check=False, movable=False)

        # Channels, Time, Z Stack, Positions and Grid widgets
        self.channel_groupbox = ChannelTable()
        self.time_groupbox = TimePlanWidget()
        self.stack_groupbox = ZStackWidget()
        self.stack_groupbox.setFixedHeight(
            self.stack_groupbox.minimumSizeHint().height()
        )
        self.position_groupbox = PositionTable()
        self.grid_groupbox = Grid()
        self.grid_groupbox.valueChanged.connect(self._update_total_time)
        self.grid_groupbox.layout().itemAt(
            self.grid_groupbox.layout().count() - 1
        ).widget().hide()  # hide add grid button
        self.grid_groupbox.setFixedHeight(self.grid_groupbox.sizeHint().height())

        # add tabs to the tab widget
        self._tab.addTab(self.channel_groupbox, "Channels")
        self._tab.addTab(self.stack_groupbox, "Z Stack")
        self._tab.addTab(self.position_groupbox, "Positions")
        self._tab.addTab(self.time_groupbox, "Time")
        self._tab.addTab(self.grid_groupbox, "Grid")

        # assign checkboxes to a variable
        self.ch_cbox = self._get_checkbox(0)
        self.z_cbox = self._get_checkbox(1)
        self.p_cbox = self._get_checkbox(2)
        self.t_cbox = self._get_checkbox(3)
        self.g_cbox = self._get_checkbox(4)

        # info time label and buttons widgets
        self.time_lbl = _MDATimeLabel()
        self.buttons_wdg = _MDAControlButtons()
        self.buttons_wdg.pause_button.hide()
        self.buttons_wdg.cancel_button.hide()
        self.buttons_wdg.run_button.hide()

        # add widgets to layout
        central_layout.addWidget(self._tab)
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
        # connect tabs
        self._tab.currentChanged.connect(self._on_tab_changed)
        # connect Channels, Time, Z Stack, Positions and Grid widgets
        self.channel_groupbox.valueChanged.connect(self._enable_run_btn)
        self.channel_groupbox.valueChanged.connect(self._update_total_time)
        self.channel_groupbox._advanced_cbox.toggled.connect(self._update_total_time)
        self.time_groupbox.valueChanged.connect(self._update_total_time)
        self.stack_groupbox.valueChanged.connect(self._update_total_time)
        self.position_groupbox._advanced_cbox.toggled.connect(self._update_total_time)
        self.position_groupbox.valueChanged.connect(self._update_total_time)
        # below not using lambda with position_groupbox below because it would cause
        # problems in closing the widget (see conftest _run_after_each_test fixture)
        # self.position_groupbox.valueChanged.connect(self._on_positions_tab_changed)
        self.position_groupbox.valueChanged.connect(lambda: self._on_tab_changed(2))
        # connect tab checkboxes
        self.ch_cbox.toggled.connect(self._enable_run_btn)
        self.ch_cbox.toggled.connect(self._update_total_time)
        self.z_cbox.toggled.connect(self._update_total_time)
        self.t_cbox.toggled.connect(self._update_total_time)
        self.p_cbox.toggled.connect(self._update_total_time)
        # not using lambda with p_cbox below because it would cause problems in closing
        # the widget (see conftest _run_after_each_test fixture)
        # self.p_cbox.toggled.connect(self._on_positions_tab_changed)
        self.p_cbox.toggled.connect(lambda: self._on_tab_changed(2))
        self.g_cbox.toggled.connect(self._update_total_time)
        # connect buttons
        self.buttons_wdg.pause_button.released.connect(self._mmc.mda.toggle_pause)
        self.buttons_wdg.cancel_button.released.connect(self._mmc.mda.cancel)
        # connect mmcore signals
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.configSet.connect(self._on_config_set)
        self._mmc.events.configGroupChanged.connect(self._on_config_set)
        self._mmc.events.channelGroupChanged.connect(self._on_channel_group_changed)
        # connect run button
        if self._include_run_button:
            self.buttons_wdg.run_button.clicked.connect(self._on_run_clicked)
            self.buttons_wdg.run_button.show()

        self._on_sys_cfg_loaded()

        self.destroyed.connect(self._disconnect)

    def _on_sys_cfg_loaded(self) -> None:
        if channel_group := self._mmc.getChannelGroup() or guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self._enable_run_btn()
        self._update_total_time()

    def _on_config_set(self, group: str, preset: str) -> None:
        if group != self._mmc.getChannelGroup():
            return
        self._enable_run_btn()

    def _on_channel_group_changed(self, group: str) -> None:
        self._enable_run_btn()

    def _get_checkbox(self, tab_index: int) -> QCheckBox:
        """Return the checkbox of the tab at the given index."""
        return self._tab.tabBar().tabButton(tab_index, self._tab.checkbox_position)

    def _on_tab_changed(self, index: int) -> None:
        """Enable/disable 'Absolute' grid modes if multiple positions are selected."""
        if index not in {2, 4}:
            return
        if self.p_cbox.isChecked() and self.position_groupbox._table.rowCount() > 1:
            if self.g_cbox.isChecked() and self.grid_groupbox.tab.currentIndex() in {
                1,
                2,
            }:
                warnings.warn(
                    "'Absolute' grid modes are not supported "
                    "with multiple positions.",
                    stacklevel=2,
                )
            self.grid_groupbox.tab.setTabEnabled(1, False)
            self.grid_groupbox.tab.setTabEnabled(2, False)
        else:
            self.grid_groupbox.tab.setTabEnabled(1, True)
            self.grid_groupbox.tab.setTabEnabled(2, True)

    def _on_positions_tab_changed(self) -> None:
        # not using .connect(lambda: self._on_tab_changed(POSITIONS))
        # because it would cause problems in closing the widget
        # (see conftest _run_after_each_test fixture)
        self._on_tab_changed(2)

    def _enable_run_btn(self) -> None:
        """Enable run button.

        ...if there is a channel group and a preset selected or the channel checkbox
        is checked and there is at least one channel selected.
        """
        if self._mmc.getChannelGroup() and self._mmc.getCurrentConfig(
            self._mmc.getChannelGroup()
        ):
            if self.ch_cbox.isChecked() and not self.channel_groupbox._table.rowCount():
                self.buttons_wdg.run_button.setEnabled(False)
            else:
                self.buttons_wdg.run_button.setEnabled(True)
        elif (
            not self.ch_cbox.isChecked() or not self.channel_groupbox._table.rowCount()
        ):
            self.buttons_wdg.run_button.setEnabled(False)
        else:
            self.buttons_wdg.run_button.setEnabled(True)

    def _enable_widgets(self, enable: bool) -> None:
        self.buttons_wdg.acquisition_order_comboBox.setEnabled(enable)
        for i in range(self._tab.count()):
            self._tab.widget(i).setEnabled(
                enable if self._get_checkbox(i).isChecked() else False
            )

    def _on_mda_started(self) -> None:
        self._enable_widgets(False)
        if self._include_run_button:
            self.buttons_wdg.pause_button.show()
            self.buttons_wdg.cancel_button.show()
        self.buttons_wdg.run_button.hide()

    def _on_mda_finished(self) -> None:
        self._enable_widgets(True)
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
            self.ch_cbox.setChecked(True)
            self.channel_groupbox.set_state([c.dict() for c in state.channels])
        else:
            self.ch_cbox.setChecked(False)

        # set z stack
        if state.z_plan:
            self.z_cbox.setChecked(True)
            self.stack_groupbox.set_state(state.z_plan.dict())
        else:
            self.z_cbox.setChecked(False)

        # set time
        if state.time_plan:
            self.t_cbox.setChecked(True)
            self.time_groupbox.set_state(state.time_plan.dict())
        else:
            self.t_cbox.setChecked(False)

        # set stage positions
        if state.stage_positions:
            self.p_cbox.setChecked(True)
            self.position_groupbox.set_state(list(state.stage_positions))
        else:
            self.p_cbox.setChecked(False)

        # set grid
        if state.grid_plan:
            self.g_cbox.setChecked(True)
            self.grid_groupbox.set_state(state.grid_plan)
        else:
            self.g_cbox.setChecked(False)

    def get_state(self) -> MDASequence:
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        channels = (
            self.channel_groupbox.value()
            if self.ch_cbox.isChecked()
            else [
                {
                    "config": self._mmc.getCurrentConfig(self._mmc.getChannelGroup()),
                    "group": self._mmc.getChannelGroup(),
                    "exposure": self._mmc.getExposure(),
                    "z_offset": 0.0,
                    "do_stack": True,
                    "acquire_every": 1,
                }
            ]
        )

        z_plan = self.stack_groupbox.value() if self.z_cbox.isChecked() else NoZ()

        time_plan = self.time_groupbox.value() if self._uses_time() else NoT()

        stage_positions: list[PositionDict] = []
        if self.p_cbox.isChecked():
            for p in self.position_groupbox.value():
                if p.get("sequence"):
                    p_sequence = MDASequence(**p.get("sequence"))  # type: ignore
                    p_sequence = p_sequence.replace(
                        axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText()
                    )
                    p["sequence"] = p_sequence

                stage_positions.append(p)

        if not stage_positions:
            stage_positions = self._get_current_position()

        grid_plan = self.grid_groupbox.value() if self.g_cbox.isChecked() else NoGrid()

        return MDASequence(
            axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText(),
            channels=channels,
            stage_positions=stage_positions,
            z_plan=z_plan,
            time_plan=time_plan,
            grid_plan=grid_plan,
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

    def _on_time_toggled(self, checked: bool) -> None:
        """Hide the warning if the time groupbox is unchecked."""
        if not checked and self.time_groupbox._warning_widget.isVisible():
            self.time_groupbox.setWarningVisible(False)
        else:
            self._update_total_time()

    def _uses_time(self) -> bool:
        """Hacky method to check whether the timebox is selected with any timepoints."""
        has_phases = self.time_groupbox.value()["phases"]  # type: ignore
        return bool(self.t_cbox.isChecked() and has_phases)

    def _update_total_time(self) -> None:
        """Calculate the minimum total acquisition time info."""
        # TODO: fix me!!!!!
        if self._mmc.getChannelGroup() and self._mmc.getCurrentConfig(
            self._mmc.getChannelGroup()
        ):
            if self.ch_cbox.isChecked() and not self.channel_groupbox._table.rowCount():
                self.time_lbl._total_time_lbl.setText(
                    "Minimum total acquisition time: 0 sec."
                )
                return

        elif (
            not self.ch_cbox.isChecked() or not self.channel_groupbox._table.rowCount()
        ):
            self.time_lbl._total_time_lbl.setText(
                "Minimum total acquisition time: 0 sec."
            )
            return

        total_time: float = 0.0
        _per_timepoints: dict[int, float] = {}
        t_per_tp_msg = ""

        for e in self.get_state():
            if e.exposure is None:
                continue

            total_time = total_time + (e.exposure / 1000)
            if self._uses_time():
                _t = e.index["t"]
                _exp = e.exposure / 1000
                _per_timepoints[_t] = _per_timepoints.get(_t, 0) + _exp

        if _per_timepoints:
            time_value = self.time_groupbox.value()

            intervals = []
            for phase in time_value["phases"]:  # type: ignore
                interval = phase["interval"].total_seconds()
                intervals.append(interval)
                if phase.get("loops") is not None:
                    total_time = total_time + (phase["loops"] - 1) * interval
                else:
                    total_time = total_time + phase["duration"].total_seconds()

            # check if the interval(s) is smaller than the sum of the exposure times
            sum_ch_exp = sum(
                (c["exposure"] / 1000)
                for c in self.channel_groupbox.value()
                if c["exposure"] is not None
            )
            for i in intervals:
                if 0 < i < sum_ch_exp:
                    self.time_groupbox.setWarningVisible(True)
                    break
                else:
                    self.time_groupbox.setWarningVisible(False)

            # group by time
            _group_by_time: dict[float, list[int]] = {
                n: [k for k in _per_timepoints if _per_timepoints[k] == n]
                for n in set(_per_timepoints.values())
            }

            t_per_tp_msg = "Minimum acquisition time per timepoint: "

            if len(_group_by_time) == 1:
                t_per_tp_msg = (
                    f"\n{t_per_tp_msg}"
                    f"{fmt_timedelta(timedelta(seconds=_per_timepoints[0]))}"
                )
            else:
                acq_min = timedelta(seconds=min(_per_timepoints.values()))
                t_per_tp_msg = (
                    f"\n{t_per_tp_msg}{fmt_timedelta(acq_min)}"
                    if self._uses_time()
                    else ""
                )
        else:
            t_per_tp_msg = ""
            # self.time_groupbox.setWarningVisible(False)

        _min_tot_time = (
            "Minimum total acquisition time: "
            f"{fmt_timedelta(timedelta(seconds=total_time))}"
        )
        self.time_lbl._total_time_lbl.setText(f"{_min_tot_time}{t_per_tp_msg}")

    def _disconnect(self) -> None:
        self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.configSet.disconnect(self._on_config_set)
        self._mmc.events.configGroupChanged.disconnect(self._on_config_set)
        self._mmc.events.channelGroupChanged.disconnect(self._on_channel_group_changed)
