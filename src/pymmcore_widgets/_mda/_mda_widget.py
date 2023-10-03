from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QTabBar,
    QVBoxLayout,
    QWidget,
)
from useq import MDASequence

from ._channel_table_widget import ChannelTable
from ._checkable_tabwidget_widget import CheckableTabWidget
from ._general_mda_widgets import (
    _AcquisitionOrderWidget,
    _MDAControlButtons,
    _SaveLoadSequenceWidget,
)
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
        parent: QWidget | None = None,
        include_run_button: bool = False,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._include_run_button = include_run_button

        # LAYOUT
        central_layout = QVBoxLayout()
        central_layout.setSpacing(7)
        central_layout.setContentsMargins(10, 10, 10, 10)

        # main TabWidget
        self._tab = CheckableTabWidget(change_tab_on_check=False)
        self._tab.setMovable(False)

        # Channels, Time, Z Stack, Positions and Grid widgets
        self.channel_widget = ChannelTable()
        self.time_widget = TimePlanWidget()
        self.stack_widget = ZStackWidget()
        self.stack_widget.setFixedHeight(self.stack_widget.minimumSizeHint().height())
        self.position_widget = PositionTable()
        self.grid_widget = Grid()
        self.grid_widget.layout().itemAt(
            self.grid_widget.layout().count() - 1
        ).widget().hide()  # hide add grid button
        self.grid_widget.setFixedHeight(self.grid_widget.sizeHint().height())

        # place widgets in a QWidget to control tab layout content margins
        wdgs = [
            (self.channel_widget, "Channels"),
            (self.stack_widget, "Z Stack"),
            (self.position_widget, "Positions"),
            (self.time_widget, "Time"),
            (self.grid_widget, "Grid"),
        ]
        for widget, title in wdgs:
            self._tab.addTab(widget, title)

        # assign checkboxes to a variable
        self.ch_cbox = self._get_checkbox(0)
        self.z_cbox = self._get_checkbox(1)
        self.p_cbox = self._get_checkbox(2)
        self.t_cbox = self._get_checkbox(3)
        self.g_cbox = self._get_checkbox(4)

        # savle load widget
        self._save_load = _SaveLoadSequenceWidget()
        self._save_load._save_button.clicked.connect(self._save_sequence)
        self._save_load._load_button.clicked.connect(self._load_sequence)

        # Acquisition order widget
        self.acquisition_order_widget = _AcquisitionOrderWidget()
        acq_order_run_layout = QHBoxLayout()
        acq_order_run_layout.addWidget(self.acquisition_order_widget)

        # add widgets to layout
        central_layout.addWidget(self._tab)
        central_layout.addWidget(self._save_load)
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
        self.layout().addLayout(acq_order_run_layout)

        # CONNECTIONS
        self._tab.currentChanged.connect(self._on_tab_changed)
        self.channel_widget.valueChanged.connect(self._enable_run_btn)
        # below not using lambda with position_widget below because it would cause
        # problems in closing the widget (see conftest _run_after_each_test fixture)
        self.position_widget.valueChanged.connect(self._on_positions_tab_changed)
        self.ch_cbox.toggled.connect(self._enable_run_btn)
        # not using lambda with p_cbox below because it would cause problems in closing
        # the widget (see conftest _run_after_each_test fixture)
        self.p_cbox.toggled.connect(self._on_positions_tab_changed)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.configSet.connect(self._on_config_set)
        self._mmc.events.configGroupChanged.connect(self._on_config_set)
        self._mmc.events.channelGroupChanged.connect(self._enable_run_btn)
        if self._include_run_button:
            self.buttons_wdg = _MDAControlButtons()
            self.buttons_wdg.run_button.clicked.connect(self._on_run_clicked)
            self.buttons_wdg.run_button.show()
            self.buttons_wdg.pause_button.released.connect(self._mmc.mda.toggle_pause)
            self.buttons_wdg.cancel_button.released.connect(self._mmc.mda.cancel)
            acq_order_run_layout.addWidget(self.buttons_wdg)

        self._on_sys_cfg_loaded()

        self.destroyed.connect(self._disconnect)

    def _on_sys_cfg_loaded(self) -> None:
        self._enable_run_btn()

    def _on_config_set(self, group: str, preset: str) -> None:
        if group != self._mmc.getChannelGroup():
            return
        self._enable_run_btn()

    def _on_channel_group_changed(self, group: str) -> None:
        self._enable_run_btn()

    def _get_checkbox(self, tab_index: int) -> QCheckBox:
        """Return the checkbox of the tab at the given index."""
        return self._tab.tabBar().tabButton(tab_index, QTabBar.ButtonPosition.LeftSide)

    def _on_tab_changed(self, index: int) -> None:
        """Enable/disable 'Absolute' grid modes if multiple positions are selected."""
        if index not in {2, 4}:
            return
        _has_positions = bool(
            self.p_cbox.isChecked() and self.position_widget._table.rowCount() > 1
        )
        self.grid_widget.tab.setTabEnabled(1, not _has_positions)
        self.grid_widget.tab.setTabEnabled(2, not _has_positions)

    def _on_positions_tab_changed(self) -> None:
        # not using .connect(lambda: self._on_tab_changed(2))
        # because it would cause problems in closing the widget
        # (see conftest _run_after_each_test fixture)
        self._on_tab_changed(2)

    def _enable_run_btn(self) -> None:
        """Enable run button.

        ...if there is a channel group and a preset selected or the channel checkbox
        is checked and there is at least one channel selected.
        """
        if not self._include_run_button:
            return

        if self._mmc.getChannelGroup() and self._mmc.getCurrentConfig(
            self._mmc.getChannelGroup()
        ):
            if self.ch_cbox.isChecked() and not self.channel_widget._table.rowCount():
                self.buttons_wdg.run_button.setEnabled(False)
            else:
                self.buttons_wdg.run_button.setEnabled(True)
        elif not self.ch_cbox.isChecked() or not self.channel_widget._table.rowCount():
            self.buttons_wdg.run_button.setEnabled(False)
        else:
            self.buttons_wdg.run_button.setEnabled(True)

    def _enable_widgets(self, enable: bool) -> None:
        self.acquisition_order_widget.acquisition_order_comboBox.setEnabled(enable)
        for i in range(self._tab.count()):
            self._get_checkbox(i).setEnabled(enable)
            self._tab.widget(i).setEnabled(
                enable if self._get_checkbox(i).isChecked() else False
            )

    def _on_mda_started(self) -> None:
        self._enable_widgets(False)

    def _on_mda_finished(self) -> None:
        self._enable_widgets(True)

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

        self.acquisition_order_widget.acquisition_order_comboBox.setCurrentText(
            "".join(state.axis_order)
        )

        # set channel table
        if state.channels:
            self.ch_cbox.setChecked(True)
            self.channel_widget.set_state([c.dict() for c in state.channels])
        else:
            self.ch_cbox.setChecked(False)

        # set z stack
        if state.z_plan:
            self.z_cbox.setChecked(True)
            self.stack_widget.set_state(state.z_plan.dict())
        else:
            self.z_cbox.setChecked(False)

        # set time
        if state.time_plan:
            self.t_cbox.setChecked(True)
            self.time_widget.set_state(state.time_plan.dict())
        else:
            self.t_cbox.setChecked(False)

        # set stage positions
        if state.stage_positions:
            self.p_cbox.setChecked(True)
            self.position_widget.set_state(list(state.stage_positions))
        else:
            self.p_cbox.setChecked(False)

        # set grid
        if state.grid_plan and not isinstance(state.grid_plan, useq.RandomPoints):
            self.g_cbox.setChecked(True)
            self.grid_widget.set_state(state.grid_plan)
        else:
            self.g_cbox.setChecked(False)

    def get_state(self) -> MDASequence:
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        if self.ch_cbox.isChecked():
            channels = self.channel_widget.value()
        else:
            group = self._mmc.getChannelGroup()
            channels = [
                useq.Channel(config=self._mmc.getCurrentConfig(group), group=group)
            ]

        stage_positions: list[PositionDict] = []
        if self.p_cbox.isChecked():
            order_combo = self.acquisition_order_widget.acquisition_order_comboBox
            axis_order = order_combo.currentText()
            for p in self.position_widget.value():
                if p.get("sequence"):
                    seq_kwargs = p.get("sequence") or {}
                    seq_kwargs["axis_order"] = axis_order
                    p_sequence = MDASequence(**seq_kwargs)
                    p["sequence"] = p_sequence  # type: ignore  # FIXME
                stage_positions.append(p)  # type: ignore

        if not stage_positions:
            stage_positions = self._get_current_position()

        mda = MDASequence(
            axis_order=(
                self.acquisition_order_widget.acquisition_order_comboBox.currentText()
            ),
            channels=channels,
            stage_positions=stage_positions,
            time_plan=self.time_widget.value() if self._uses_time() else None,
            grid_plan=self.grid_widget.value() if self.g_cbox.isChecked() else None,
            z_plan=self.stack_widget.value() if self.z_cbox.isChecked() else None,
        )
        return mda

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

    def _save_sequence(self) -> None:
        """Save the current MDA sequence to a json file."""
        (dir_file, _) = QFileDialog.getSaveFileName(
            self, "Saving directory and filename.", "", "json(*.json)"
        )
        if not dir_file:
            return

        with open(str(dir_file), "w") as file:
            file.write(self.get_state().json())

    def _load_sequence(self) -> None:
        """Load a MDAsequence json file into the widget."""
        (filename, _) = QFileDialog.getOpenFileName(
            self, "Select a MDAsequence json file.", "", "json(*.json)"
        )
        if filename:
            import json

            with open(filename) as file:
                self.set_state(json.load(file))

    def _on_time_toggled(self, checked: bool) -> None:
        """Hide the warning if the time groupbox is unchecked."""
        if not checked and self.time_widget._warning_widget.isVisible():
            self.time_widget.setWarningVisible(False)

    def _uses_time(self) -> bool:
        """Hacky method to check whether the timebox is selected with any timepoints."""
        has_phases = self.time_widget._table.rowCount()
        return bool(self.t_cbox.isChecked() and has_phases)

    def _uses_autofocus(self) -> bool:
        return bool(self.p_cbox.isChecked() and self.position_widget._use_af())

    def _disconnect(self) -> None:
        self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.configSet.disconnect(self._on_config_set)
        self._mmc.events.configGroupChanged.disconnect(self._on_config_set)
        self._mmc.events.channelGroupChanged.disconnect(self._on_channel_group_changed)
        self._mmc.events.channelGroupChanged.disconnect(self._enable_run_btn)

    # DEPRECATIONS

    @property
    def channel_groupbox(self) -> ChannelTable:
        warnings.warn(
            "MDAWidget.channel_groupbox has been renamed to MDAWidget.channel_widget. "
            "In the future, this will raise an exception.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.channel_widget.isChecked = lambda: _is_checked(self.channel_widget)
        return self.channel_widget

    @property
    def position_groupbox(self) -> PositionTable:
        warnings.warn(
            "MDAWidget.position_groupbox has been renamed to MDAWidget.position_widget."
            " In the future, this will raise an exception.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.position_widget.isChecked = lambda: _is_checked(self.position_widget)
        return self.position_widget

    @property
    def time_groupbox(self) -> ChannelTable:
        warnings.warn(
            "MDAWidget.time_groupbox has been renamed to MDAWidget.time_widget. "
            "In the future, this will raise an exception.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.time_widget.isChecked = lambda: _is_checked(self.time_widget)
        return self.time_widget

    @property
    def stack_groupbox(self) -> PositionTable:
        warnings.warn(
            "MDAWidget.stack_groupbox has been renamed to MDAWidget.stack_widget."
            " In the future, this will raise an exception.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.stack_widget.isChecked = lambda: _is_checked(self.stack_widget)
        return self.stack_widget


def _is_checked(self: QWidget) -> bool:
    from qtpy.QtWidgets import QTabWidget

    p = self.parent()
    tab = None
    while p:
        if isinstance(p, QTabWidget):
            tab = p
            break
        p = p.parent()
    if not tab:
        return False
    my_idx = tab.indexOf(self)
    chbox = tab.tabBar().tabButton(my_idx, tab.checkbox_position)
    return chbox.isChecked()  # type: ignore
