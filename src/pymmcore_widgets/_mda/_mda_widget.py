from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import create_worker, signals_blocked
from useq import MDASequence, NoGrid, NoT, NoZ  # type: ignore

from .._util import _select_output_unit, guess_channel_group
from ._channel_table_widget import ChannelTable
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

GROUP_STYLE = (
    "QGroupBox::indicator {border: 0px; width: 0px; height: 0px; border-radius: 0px;}"
)


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

        # Widgets for Channels, Time, ZStack, and Positions in the Scroll Area
        self.channel_groupbox = ChannelTable()
        self.channel_groupbox.setTitle("")
        self.channel_groupbox.setEnabled(False)
        self.channel_groupbox.valueChanged.connect(self._enable_run_btn)
        self.channel_groupbox._advanced_cbox.toggled.connect(self._update_total_time)

        self.time_groupbox = TimePlanWidget()
        self.time_groupbox.setTitle("")
        self.time_groupbox.setCheckable(False)
        self.time_groupbox.setEnabled(False)
        self.time_groupbox.setStyleSheet(GROUP_STYLE)
        self.time_groupbox.toggled.connect(self._update_total_time)
        self.time_groupbox.toggled.connect(self._on_time_toggled)

        self.stack_groupbox = ZStackWidget()
        self.stack_groupbox.setTitle("")
        self.stack_groupbox.setCheckable(False)
        self.stack_groupbox.setEnabled(False)
        self.stack_groupbox.setStyleSheet(GROUP_STYLE)
        self.stack_groupbox.toggled.connect(self._update_total_time)

        self.position_groupbox = PositionTable()
        self.position_groupbox.setTitle("")
        self.position_groupbox.setCheckable(False)
        self.position_groupbox.setEnabled(False)
        self.position_groupbox.setStyleSheet(GROUP_STYLE)
        self.position_groupbox.toggled.connect(self._update_total_time)

        self.grid_groupbox = QGroupBox()
        self.grid_groupbox.setLayout(QVBoxLayout())
        self.grid_groupbox.layout().setContentsMargins(0, 0, 0, 0)
        self.grid_groupbox.layout().setSpacing(0)
        self.grid_groupbox.setTitle("")
        self.grid_groupbox.setEnabled(False)
        self.grid_groupbox.setStyleSheet(GROUP_STYLE)
        self._mda_grid_wdg = Grid()
        self._mda_grid_wdg.valueChanged.connect(self._update_total_time)
        self.grid_groupbox.layout().addWidget(self._mda_grid_wdg)
        self._mda_grid_wdg.layout().itemAt(
            self._mda_grid_wdg.layout().count() - 1
        ).widget().hide()  # hide add grid button
        self._mda_grid_wdg.setMinimumHeight(self._mda_grid_wdg.sizeHint().height())

        # below the scroll area, tabs, some feedback widgets and buttons
        self.time_lbl = _MDATimeLabel()

        self.buttons_wdg = _MDAControlButtons()
        self.buttons_wdg.pause_button.hide()
        self.buttons_wdg.cancel_button.hide()
        self.buttons_wdg.run_button.hide()

        # LAYOUT
        central_layout = QVBoxLayout()
        central_layout.setSpacing(20)
        central_layout.setContentsMargins(10, 10, 10, 10)

        # TABS
        self._tab = QTabWidget()

        self._checkbox_channel = QCheckBox("")
        self._checkbox_channel.setObjectName("Channels")
        self._checkbox_channel.toggled.connect(self._on_tab_checkbox_toggled)
        self._checkbox_z = QCheckBox("")
        self._checkbox_z.setObjectName("ZStack")
        self._checkbox_z.toggled.connect(self._on_tab_checkbox_toggled)
        self._checkbox_time = QCheckBox("")
        self._checkbox_time.setObjectName("Time")
        self._checkbox_time.toggled.connect(self._on_tab_checkbox_toggled)
        self._checkbox_position = QCheckBox("")
        self._checkbox_position.setObjectName("Positions")
        self._checkbox_position.toggled.connect(self._on_tab_checkbox_toggled)
        self._checkbox_grid = QCheckBox("")
        self._checkbox_grid.setObjectName("Grid")
        self._checkbox_grid.toggled.connect(self._on_tab_checkbox_toggled)

        self._tabbar = TabBar(checkbox_width=self._checkbox_channel.sizeHint().width())

        # set channel tab with checkbox
        cwdg = QWidget()
        cwdg.setLayout(QVBoxLayout())
        cwdg.layout().setContentsMargins(10, 10, 10, 10)
        cwdg.layout().setSpacing(0)
        cwdg.layout().addWidget(self.channel_groupbox)
        self._tab.addTab(cwdg, "")
        self._tabbar.addTab("Channels")
        self._tabbar.setTabButton(
            0, QTabBar.ButtonPosition.LeftSide, self._checkbox_channel
        )

        # set zstack tab with checkbox
        zwdg = QWidget()
        zwdg.setLayout(QVBoxLayout())
        zwdg.layout().setContentsMargins(10, 10, 10, 10)
        zwdg.layout().setSpacing(0)
        zwdg.layout().addWidget(self.stack_groupbox)
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        zwdg.layout().addSpacerItem(spacer)
        self._tab.addTab(zwdg, "")
        self._tabbar.addTab("Z Stack")
        self._tabbar.setTabButton(1, QTabBar.ButtonPosition.LeftSide, self._checkbox_z)

        # set positions tab with checkbox
        pwdg = QWidget()
        pwdg.setLayout(QVBoxLayout())
        pwdg.layout().setContentsMargins(10, 10, 10, 10)
        pwdg.layout().setSpacing(0)
        pwdg.layout().addWidget(self.position_groupbox)
        self._tab.addTab(pwdg, "")
        self._tabbar.addTab("Positions")
        self._tabbar.setTabButton(
            2, QTabBar.ButtonPosition.LeftSide, self._checkbox_position
        )

        # set time tab with checkbox
        twdg = QWidget()
        twdg.setLayout(QVBoxLayout())
        twdg.layout().setContentsMargins(10, 10, 10, 10)
        twdg.layout().setSpacing(0)
        twdg.layout().addWidget(self.time_groupbox)
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        twdg.layout().addSpacerItem(spacer)
        self._tab.addTab(twdg, "")
        self._tabbar.addTab("Time")
        self._tabbar.setTabButton(
            3, QTabBar.ButtonPosition.LeftSide, self._checkbox_time
        )

        # set grid tab with checkbox
        gwdg = QWidget()
        gwdg.setLayout(QVBoxLayout())
        gwdg.layout().setContentsMargins(10, 10, 10, 10)
        gwdg.layout().setSpacing(0)
        gwdg.layout().addWidget(self.grid_groupbox)
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        gwdg.layout().addSpacerItem(spacer)
        self._tab.addTab(gwdg, "")
        self._tabbar.addTab("Grid")
        self._tabbar.setTabButton(
            4, QTabBar.ButtonPosition.LeftSide, self._checkbox_grid
        )

        self._tab.setTabBar(self._tabbar)

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
        # connect buttons
        self.buttons_wdg.pause_button.released.connect(self._mmc.mda.toggle_pause)
        self.buttons_wdg.cancel_button.released.connect(self._mmc.mda.cancel)
        # connect valueUpdated signal
        self.channel_groupbox.valueChanged.connect(self._update_total_time)
        self.stack_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.valueChanged.connect(self._update_total_time)
        self.time_groupbox.toggled.connect(self._update_total_time)
        self.position_groupbox.valueChanged.connect(self._update_total_time)
        # below not using
        # position_groupbox.valueChanged.connect(lambda: self._on_tab_changed(2))
        # because it would cause problems in closing the widget
        # (see conftest _run_after_each_test fixture)
        self.position_groupbox.valueChanged.connect(self._on_pos_tab_changed)
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

    def _on_tab_changed(self, index: int) -> None:
        if index not in {2, 4}:
            return
        if (
            self._checkbox_position.isChecked()
            and self.position_groupbox._table.rowCount() > 1
        ):
            if (
                self._checkbox_grid.isChecked()
                and self._mda_grid_wdg.tab.currentIndex() in {1, 2}
            ):
                warnings.warn(
                    "'Absolute' grid modes are not supported "
                    "with multiple positions."
                )
                with signals_blocked(self._checkbox_grid):
                    self._checkbox_grid.setChecked(False)
                    self.grid_groupbox.setEnabled(False)
            self._mda_grid_wdg.tab.setTabEnabled(1, False)
            self._mda_grid_wdg.tab.setTabEnabled(2, False)
        else:
            self._mda_grid_wdg.tab.setTabEnabled(1, True)
            self._mda_grid_wdg.tab.setTabEnabled(2, True)

    def _on_pos_tab_changed(self) -> None:
        # not using .connect(lambda: self._on_tab_changed(2)) because it would
        # cause problems in closing the widget
        # (see conftest _run_after_each_test fixture)
        self._on_tab_changed(2)

    def _on_tab_checkbox_toggled(self, checked: bool) -> None:
        _sender = self.sender().objectName()
        if _sender == "Channels":
            self._tab.setCurrentIndex(0)
            self.channel_groupbox.setEnabled(checked)
            self._enable_run_btn()
            self._update_total_time()
        elif _sender == "ZStack":
            self._tab.setCurrentIndex(1)
            self.stack_groupbox.setEnabled(checked)
        elif _sender == "Positions":
            self._tab.setCurrentIndex(2)
            self.position_groupbox.setEnabled(checked)
            self._on_pos_tab_changed()
        elif _sender == "Time":
            self._tab.setCurrentIndex(3)
            self.time_groupbox.setEnabled(checked)
        elif _sender == "Grid":
            self._tab.setCurrentIndex(4)
            self.grid_groupbox.setEnabled(checked)
            self._update_total_time()

    def _enable_run_btn(self) -> None:
        """Enable run button.

        ...if there is a channel group and a preset selected or the channel checkbox
        is checked and there is at least one channel selected.
        """
        if self._mmc.getChannelGroup() and self._mmc.getCurrentConfig(
            self._mmc.getChannelGroup()
        ):
            if (
                self._checkbox_channel.isChecked()
                and not self.channel_groupbox._table.rowCount()
            ):
                self.buttons_wdg.run_button.setEnabled(False)
            else:
                self.buttons_wdg.run_button.setEnabled(True)

        elif (
            not self._checkbox_channel.isChecked()
            or not self.channel_groupbox._table.rowCount()
        ):
            self.buttons_wdg.run_button.setEnabled(False)

        else:
            self.buttons_wdg.run_button.setEnabled(True)

    def _set_enabled(self, enabled: bool) -> None:
        self._checkbox_channel.setEnabled(enabled)
        self._checkbox_z.setEnabled(enabled)
        self._checkbox_position.setEnabled(enabled)
        self._checkbox_time.setEnabled(enabled)
        self._checkbox_grid.setEnabled(enabled)

        self.time_groupbox.setEnabled(
            enabled if self._checkbox_time.isChecked() else False
        )
        self.buttons_wdg.acquisition_order_comboBox.setEnabled(enabled)
        self.channel_groupbox.setEnabled(
            enabled if self._checkbox_channel.isChecked() else False
        )

        if not self._mmc.getXYStageDevice():
            self._checkbox_position.setChecked(False)
            self.position_groupbox.setEnabled(False)
            self._checkbox_grid.setEnabled(False)
            self.grid_groupbox.setEnabled(False)
        else:
            self.position_groupbox.setEnabled(
                enabled if self._checkbox_position.isChecked() else False
            )
            self.grid_groupbox.setEnabled(
                enabled if self._checkbox_grid.isChecked() else False
            )

        if not self._mmc.getFocusDevice():
            self._checkbox_z.setChecked(False)
            self.stack_groupbox.setEnabled(False)
        else:
            self.stack_groupbox.setEnabled(
                enabled if self._checkbox_z.isChecked() else False
            )

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
            self._checkbox_channel.setChecked(True)
            self.channel_groupbox.set_state([c.dict() for c in state.channels])

        # set Z
        if state.z_plan:
            self._checkbox_z.setChecked(True)
            self.stack_groupbox.set_state(state.z_plan.dict())
        else:
            self._checkbox_z.setChecked(False)

        # set time
        if state.time_plan:
            self._checkbox_time.setChecked(True)
            self.time_groupbox.set_state(state.time_plan.dict())
        else:
            self._checkbox_time.setChecked(False)

        # set stage positions
        if state.stage_positions:
            self._checkbox_position.setChecked(True)
            self.position_groupbox.set_state(list(state.stage_positions))
        else:
            self._checkbox_position.setChecked(False)

        # set grid
        if state.grid_plan:  # type: ignore
            self._checkbox_grid.setChecked(True)
            self._mda_grid_wdg.set_state(state.grid_plan)  # type: ignore
        else:
            self._checkbox_grid.setChecked(False)

    def get_state(self) -> MDASequence:
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        channels = (
            self.channel_groupbox.value()
            if self._checkbox_channel.isChecked()
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

        z_plan = self.stack_groupbox.value() if self._checkbox_z.isChecked() else NoZ()

        time_plan = (
            self.time_groupbox.value() if self._checkbox_time.isChecked() else NoT()
        )

        stage_positions: list[PositionDict] = []
        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        width = int(width * self._mmc.getPixelSizeUm())
        height = int(height * self._mmc.getPixelSizeUm())
        if self._checkbox_position.isChecked():
            for p in self.position_groupbox.value():
                if p.get("sequence"):
                    p_sequence = MDASequence(**p.get("sequence"))  # type: ignore
                    p_sequence = p_sequence.replace(
                        axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText()
                    )
                    p_sequence.set_fov_size((width, height))  # type: ignore
                    p["sequence"] = p_sequence

                stage_positions.append(p)

        if not stage_positions:
            stage_positions = self._get_current_position()

        grid_plan = (
            self._mda_grid_wdg.value() if self._checkbox_grid.isChecked() else NoGrid()
        )

        sequence = MDASequence(
            axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText(),
            channels=channels,
            stage_positions=stage_positions,
            z_plan=z_plan,
            time_plan=time_plan,
            grid_plan=grid_plan,
        )
        sequence.set_fov_size((width, height))  # type: ignore

        return sequence

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

    def _update_total_time(self) -> None:
        # create thread to avoid blocking the UI
        create_worker(self._calculate_minimum_acquisition_time, _start_thread=True)

    def _calculate_minimum_acquisition_time(self) -> None:
        """Calculate the minimum total acquisition time info."""
        if self._mmc.getChannelGroup() and self._mmc.getCurrentConfig(
            self._mmc.getChannelGroup()
        ):
            if (
                self._checkbox_channel.isChecked()
                and not self.channel_groupbox._table.rowCount()
            ):
                self.time_lbl._total_time_lbl.setText(
                    "Minimum total acquisition time: 0 sec."
                )
                return

        elif (
            not self._checkbox_channel.isChecked()
            or not self.channel_groupbox._table.rowCount()
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

            print(e.exposure)

            total_time = total_time + (e.exposure / 1000)
            if self._checkbox_time.isChecked():
                _t = e.index["t"]
                _exp = e.exposure / 1000
                _per_timepoints[_t] = _per_timepoints.get(_t, 0) + _exp

        if _per_timepoints:
            time_value = self.time_groupbox.value()
            timepoints = time_value["loops"]
            interval = time_value["interval"].total_seconds()
            total_time = total_time + (timepoints - 1) * interval

            # check if the interval is smaller than the sum of the exposure times
            sum_ch_exp = sum(
                (c["exposure"] / 1000)
                for c in self.channel_groupbox.value()
                if c["exposure"] is not None
            )
            self.time_groupbox.setWarningVisible(0 < interval < sum_ch_exp)

            # group by time
            _group_by_time: dict[float, list[int]] = {
                n: [k for k in _per_timepoints if _per_timepoints[k] == n]
                for n in set(_per_timepoints.values())
            }

            t_per_tp_msg = "\nMinimum acquisition time(s) per timepoint: "
            if len(_group_by_time) == 1:
                min_aq_tp, _tp_unit = _select_output_unit(float(_per_timepoints[0]))
                t_per_tp_msg = f"{t_per_tp_msg}{min_aq_tp:.4f} {_tp_unit}."
            else:
                # print longest timepoint first and other in brackets
                _tp = []
                for idx, i in enumerate(sorted(_per_timepoints.values(), reverse=True)):
                    aq, u = _select_output_unit(float(i))
                    if idx == 0:
                        t_per_tp_msg = f"{t_per_tp_msg}{aq:.4f} {u} ("
                    elif (aq, u) in _tp:
                        continue
                    else:
                        t_per_tp_msg = f"{t_per_tp_msg}{aq:.4f} {u},  "
                    _tp.append((aq, u))
                t_per_tp_msg = f"{t_per_tp_msg[:-3]})."

        _min_tot_time, _unit = _select_output_unit(total_time)
        tot_acq_msg = f"Minimum total acquisition time: {_min_tot_time:.4f} {_unit}."
        self.time_lbl._total_time_lbl.setText(f"{tot_acq_msg}{t_per_tp_msg}")

    def _disconnect(self) -> None:
        self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.configSet.disconnect(self._on_config_set)
        self._mmc.events.configGroupChanged.disconnect(self._on_config_set)
        self._mmc.events.channelGroupChanged.disconnect(self._on_channel_group_changed)
