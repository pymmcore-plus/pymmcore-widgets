from __future__ import annotations

from importlib.util import find_spec
from itertools import permutations
from pathlib import Path
from typing import cast

import useq
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

import pymmcore_widgets
from pymmcore_widgets.useq_widgets._channels import ChannelTable
from pymmcore_widgets.useq_widgets._checkable_tabwidget_widget import CheckableTabWidget
from pymmcore_widgets.useq_widgets._grid import GridPlanWidget
from pymmcore_widgets.useq_widgets._positions import PositionTable
from pymmcore_widgets.useq_widgets._time import TimePlanWidget
from pymmcore_widgets.useq_widgets._z import ZPlanWidget

try:
    from pint import Quantity

    def _format_duration(duration: float) -> str:
        d = Quantity(duration, "s").to_compact()
        return f"{d:.1f~#P}" if d else ""

except ImportError:  # pragma: no cover

    def _format_duration(duration: float) -> str:
        return f"{duration:.3f} s" if duration else ""


def _check_order(x: str, first: str, second: str) -> bool:
    return first in x and second in x and x.index(first) > x.index(second)


PYMMCW_METADATA_KEY = "pymmcore_widgets"
NULL_SEQUENCE = useq.MDASequence()
AXES = "tpgcz"
ALLOWED_ORDERS = {"".join(p) for x in range(1, 6) for p in permutations(AXES, x)}
for x in list(ALLOWED_ORDERS):
    for first, second in (
        ("t", "z"),  # t cannot come after z
        ("p", "g"),  # p cannot come after g
        ("p", "c"),  # p cannot come after c
        ("p", "z"),  # p cannot come after z
        ("g", "z"),  # g cannot come after z
    ):
        if _check_order(x, first, second):
            ALLOWED_ORDERS.discard(x)


class MDATabs(CheckableTabWidget):
    """Checkable QTabWidget for editing a useq.MDASequence.

    It contains a Tab for each of the MDASequence, axis (channels, positions, etc...).
    """

    time_plan: TimePlanWidget
    stage_positions: PositionTable
    grid_plan: GridPlanWidget
    z_plan: ZPlanWidget
    channels: ChannelTable

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # self.setMovable(True)
        self.tabChecked.connect(self._on_tab_checked)

        self.create_subwidgets()

        self.addTab(self.time_plan, "Time", checked=False)
        self.addTab(self.stage_positions, "Positions", checked=False)
        self.addTab(self.grid_plan, "Grid", checked=False)
        self.addTab(self.z_plan, "Z Stack", checked=False)
        self.addTab(self.channels, "Channels", checked=False)
        self.setCurrentIndex(self.indexOf(self.channels))

        # we only show the DO_STACK and ACQUIRE_EVERY columns when the
        # corresponding tab is checked
        ch_table = self.channels.table()
        ch_table.hideColumn(ch_table.indexOf(self.channels.DO_STACK))
        ch_table.hideColumn(ch_table.indexOf(self.channels.ACQUIRE_EVERY))

    def create_subwidgets(self) -> None:
        """Create the Tabs of the widget."""
        self.time_plan = TimePlanWidget(1)
        self.stage_positions = PositionTable(1)
        self.grid_plan = GridPlanWidget()
        self.z_plan = ZPlanWidget()
        self.channels = ChannelTable(1)

    def isAxisUsed(self, key: str | QWidget) -> bool:
        """Return True if the given axis is used in the sequence.

        Parameters
        ----------
        key : str | QWidget
            The axis to check. Can be one of "c", "t", "p", "g", "z", or the
            corresponding widget instance (e.g. self.channels, etc...)
        """
        if isinstance(key, str):
            _map: dict[str, QWidget] = {
                "c": self.channels,
                "t": self.time_plan,
                "p": self.stage_positions,
                "z": self.z_plan,
                "g": self.grid_plan,
            }
            if (lower_key := key[0].lower()) in _map:
                key = _map[lower_key]
            else:
                raise ValueError(f"Invalid key: {key!r}")  # pragma: no cover
        return bool(self.isChecked(key))

    def usedAxes(self) -> tuple[str, ...]:
        """Return a tuple of the axes currently used in the sequence."""
        return tuple(k for k in ("tpgzc") if self.isAxisUsed(k))

    def value(self) -> useq.MDASequence:
        """Return the current sequence as a [`useq.MDASequence`][]."""
        return useq.MDASequence(
            z_plan=self.z_plan.value() if self.isAxisUsed("z") else None,
            time_plan=self.time_plan.value() if self.isAxisUsed("t") else None,
            stage_positions=(
                self.stage_positions.value() if self.isAxisUsed("p") else ()
            ),
            channels=self.channels.value() if self.isAxisUsed("c") else (),
            grid_plan=self.grid_plan.value() if self.isAxisUsed("g") else None,
            metadata={PYMMCW_METADATA_KEY: {"version": pymmcore_widgets.__version__}},
        )

    def setValue(self, value: useq.MDASequence) -> None:
        """Set widget value from a [`useq.MDASequence`][]."""
        if not isinstance(value, useq.MDASequence):  # pragma: no cover
            raise TypeError(f"Expected useq.MDASequence, got {type(value)}")

        widget: (
            ChannelTable | TimePlanWidget | ZPlanWidget | PositionTable | GridPlanWidget
        )
        for f in ("channels", "time_plan", "z_plan", "stage_positions", "grid_plan"):
            widget = getattr(self, f)
            if field_val := getattr(value, f):
                widget.setValue(field_val)
                self.setChecked(widget, True)
            else:
                # widget.setValue(None)
                self.setChecked(widget, False)

    def _on_tab_checked(self, idx: int, checked: bool) -> None:
        """Handle tabChecked signal.

        Hide columns in the channels tab accordingly.
        """
        _map = {
            self.indexOf(self.z_plan): self.channels.DO_STACK,
            self.indexOf(self.time_plan): self.channels.ACQUIRE_EVERY,
        }
        if idx in _map:
            ch_table = self.channels.table()
            ch_table.setColumnHidden(ch_table.indexOf(_map[idx]), not checked)


class AutofocusAxis(QWidget):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        lbl = QLabel("Use Hardware Autofocus on Axis:")
        self.use_af_p = QCheckBox("p")
        self.use_af_t = QCheckBox("t")
        self.use_af_g = QCheckBox("g")

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)
        layout.addWidget(self.use_af_p)
        layout.addWidget(self.use_af_t)
        layout.addWidget(self.use_af_g)
        layout.addStretch()

        self.use_af_p.toggled.connect(self.valueChanged)
        self.use_af_t.toggled.connect(self.valueChanged)
        self.use_af_g.toggled.connect(self.valueChanged)

        self.setToolTip("Use Hardware Autofocus on the selected axes.")

    def value(self) -> tuple[str, ...]:
        """Return the autofocus axes."""
        af_axis: tuple[str, ...] = ()
        if self.use_af_p.isChecked():
            af_axis += ("p",)
        if self.use_af_t.isChecked():
            af_axis += ("t",)
        if self.use_af_g.isChecked():
            af_axis += ("g",)
        return af_axis

    def setValue(self, value: tuple[str, ...]) -> None:
        """Set widget value from a tuple of autofocus axes."""
        self.use_af_p.setChecked("p" in value)
        self.use_af_t.setChecked("t" in value)
        self.use_af_g.setChecked("g" in value)


class KeepShutterOpen(QWidget):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        lbl = QLabel("Keep Shutter Open Across Axis:")
        self.leave_open_t = QCheckBox("t")
        self.leave_open_z = QCheckBox("z")

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)
        layout.addWidget(self.leave_open_z)
        layout.addWidget(self.leave_open_t)
        layout.addStretch()

        self.leave_open_t.toggled.connect(self.valueChanged)
        self.leave_open_z.toggled.connect(self.valueChanged)

        self.setToolTip("Keep the shutter open across the selected axes.")

    def value(self) -> tuple[str, ...]:
        """Return the axes to keep the shutter open across."""
        shutters: tuple[str, ...] = ()
        if self.leave_open_z.isChecked() and self.leave_open_z.isEnabled():
            shutters += ("z",)
        if self.leave_open_t.isChecked() and self.leave_open_t.isEnabled():
            shutters += ("t",)
        return shutters

    def setValue(self, value: tuple[str, ...]) -> None:
        """Set widget value from a tuple of axes to keep the shutter open across."""
        self.leave_open_z.setChecked("z" in value)
        self.leave_open_t.setChecked("t" in value)


class MDASequenceWidget(QWidget):
    """A widget that provides a GUI to construct and edit a [`useq.MDASequence`][].

    This widget requires no connection to a microscope or core instance.  It strictly
    deals with loading and creating `useq-schema` [`useq.MDASequence`][] objects.
    """

    valueChanged = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        tab_widget: MDATabs | None = None,
    ) -> None:
        super().__init__(parent)

        # -------------- Main MDA Axis Widgets --------------

        self.tab_wdg = tab_widget or MDATabs(self)

        self.axis_order = QComboBox()
        self.axis_order.setToolTip("Slowest to fastest axis order.")
        self.axis_order.setMinimumWidth(80)

        # -------------- Other Widgets --------------

        # QLabel with standard warning icon to indicate time overflow
        style = self.style()
        warning_icon = style.standardIcon(style.StandardPixmap.SP_MessageBoxWarning)
        self._time_warning = QLabel()
        self._time_warning.setToolTip(
            "The current settings will be unable to satisfy<br>"
            "the time interval requested in the time tab."
        )
        self._time_warning.setPixmap(warning_icon.pixmap(24, 24))
        self._time_warning.hide()
        self._duration_label = QLabel()
        self._duration_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._duration_label.setWordWrap(True)

        self._save_button = QPushButton("Save Settings")
        self._save_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._save_button.clicked.connect(self.save)
        self._load_button = QPushButton("Load Settings")
        self._load_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._load_button.clicked.connect(self.load)

        # -------------- Main Layout --------------

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Axis Order:"))
        top_row.addWidget(self.axis_order)
        top_row.addStretch()

        self.keep_shutter_open = KeepShutterOpen()
        self.af_axis = AutofocusAxis()
        cbox_row = QVBoxLayout()
        cbox_row.setContentsMargins(0, 0, 0, 0)
        cbox_row.setSpacing(5)
        cbox_row.addWidget(self.keep_shutter_open)
        cbox_row.addWidget(self.af_axis)
        cbox_row.addStretch()

        bot_row = QHBoxLayout()
        bot_row.addWidget(self._time_warning)
        bot_row.addWidget(self._duration_label)
        bot_row.addWidget(self._save_button)
        bot_row.addWidget(self._load_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.tab_wdg, 1)
        layout.addLayout(cbox_row)
        layout.addLayout(bot_row)

        # -------------- Connections --------------

        self.channels.valueChanged.connect(self.valueChanged)
        self.time_plan.valueChanged.connect(self.valueChanged)
        self.stage_positions.valueChanged.connect(self.valueChanged)
        self.z_plan.valueChanged.connect(self.valueChanged)
        self.grid_plan.valueChanged.connect(self.valueChanged)
        self.tab_wdg.tabChecked.connect(self._update_available_axis_orders)
        self.axis_order.currentTextChanged.connect(self.valueChanged)
        self.valueChanged.connect(self._update_time_estimate)

        self.keep_shutter_open.valueChanged.connect(self.valueChanged)
        self.af_axis.valueChanged.connect(self.valueChanged)
        self.stage_positions.af_per_position.toggled.connect(self._on_af_toggled)

        with signals_blocked(self):
            self.tab_wdg.setChecked(self.channels, True)

    # ----------- Aliases for tab_wdg widgets -----------

    @property
    def channels(self) -> ChannelTable:
        return self.tab_wdg.channels

    @property
    def time_plan(self) -> TimePlanWidget:
        return self.tab_wdg.time_plan

    @property
    def z_plan(self) -> ZPlanWidget:
        return self.tab_wdg.z_plan

    @property
    def stage_positions(self) -> PositionTable:
        return self.tab_wdg.stage_positions

    @property
    def grid_plan(self) -> GridPlanWidget:
        return self.tab_wdg.grid_plan

    # -------------- Public API --------------

    def value(self) -> useq.MDASequence:
        """Return the current value of the widget as a [`useq.MDASequence`][].

        Returns
        -------
        useq.MDASequence
            The current [`useq.MDASequence`][] value of the widget.
        """
        val = self.tab_wdg.value()

        # things to update
        replace: dict = {
            # update mda axis order
            "axis_order": self.axis_order.currentText(),
            # update keep_shutter_open_across
            "keep_shutter_open_across": self.keep_shutter_open.value(),
        }

        if self.stage_positions.af_per_position.isChecked():
            # check if the autofocus offsets are the same for all positions
            # and simplify to a single global autofocus plan if so.
            replace.update(self._simplify_af_offsets(val))
        elif af_axes := self.af_axis.value():
            # otherwise use selected af axes as global autofocus plan
            replace["autofocus_plan"] = useq.AxesBasedAF(axes=af_axes)

        if replace:
            val = val.replace(**replace)

        return val

    def setValue(self, value: useq.MDASequence) -> None:
        """Set the current value of the widget from a [`useq.MDASequence`][].

        Parameters
        ----------
        value : useq.MDASequence
            The [`useq.MDASequence`][] to set.
        """
        self.tab_wdg.setValue(value)

        keep_shutter_open = value.keep_shutter_open_across
        self.keep_shutter_open.setValue(keep_shutter_open)

        # update autofocus axes checkboxes
        axis: set[str] = set()
        # update from global autofocus plan
        if value.autofocus_plan:
            axis.update(value.autofocus_plan.axes)
        # update from autofocus plans in each position sub-sequence
        if value.stage_positions:
            for pos in value.stage_positions:
                if pos.sequence and pos.sequence.autofocus_plan:
                    axis.update(pos.sequence.autofocus_plan.axes)
        self.af_axis.setValue(tuple(axis))
        axis_text = "".join(x for x in value.axis_order if x in self.tab_wdg.usedAxes())
        self.axis_order.setCurrentText(axis_text)

    def save(self, file: str | Path | None = None) -> None:
        """Save the current [`useq.MDASequence`][] to a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getSaveFileName(
                self,
                "Save MDASequence and filename.",
                "",
                self._settings_extensions(),
            )
            if not file:  # pragma: no cover
                return

        dest = Path(file)
        if not dest.suffix:
            dest = dest.with_suffix(".yaml")
        if dest.suffix in {".yaml", ".yml"}:
            yaml = self.value().yaml(exclude_unset=True, exclude_defaults=True)
            data = cast("str", yaml)
        elif dest.suffix == ".json":
            data = self.value().model_dump_json(
                exclude_unset=True, exclude_defaults=True
            )
        else:  # pragma: no cover
            raise ValueError(f"Invalid file extension: {dest.suffix!r}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(data)

    def load(self, file: str | Path | None = None) -> None:
        """Load a [`useq.MDASequence`][] from a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getOpenFileName(
                self,
                "Select an MDAsequence file.",
                "",
                self._settings_extensions(),
            )
            if not file:  # pragma: no cover
                return

        src = Path(file)
        if not src.is_file():  # pragma: no cover
            raise FileNotFoundError(f"File not found: {src}")

        try:
            mda_seq = useq.MDASequence.from_file(src)
        except Exception as e:  # pragma: no cover
            raise ValueError(f"Failed to load MDASequence file: {src}") from e

        self.setValue(mda_seq)

    # -------------- Private API --------------

    def _settings_extensions(self) -> str:
        """Returns the available extensions for MDA settings save/load."""
        if find_spec("yaml") is not None:
            # YAML available
            return "All (*.yaml *yml *.json);;YAML (*.yaml *.yml);;JSON (*.json)"
        # Only JSON
        return "All (*.json);;JSON (*.json)"

    def _on_af_toggled(self, checked: bool) -> None:
        # if the 'af_per_position' checkbox in the PositionTable is checked, set checked
        # also the autofocus p axis checkbox.
        if checked and self.tab_wdg.isChecked(self.stage_positions):
            self.af_axis.use_af_p.setChecked(True)

    def _update_available_axis_orders(self) -> None:
        """Handle tabChecked signal.

        Hide columns in the channels tab accordingly.
        """
        with signals_blocked(self.axis_order):
            self.axis_order.clear()

            # show allowed permutations of selected axes
            for p in permutations(self.tab_wdg.usedAxes()):
                if (strp := "".join(p)) in ALLOWED_ORDERS:
                    self.axis_order.addItem(strp)

            self.axis_order.setEnabled(self.axis_order.count() > 1)

        self.valueChanged.emit()

    def _update_time_estimate(self) -> None:
        """Update the time estimate label."""
        val = self.value()
        try:
            self._time_estimate = val.estimate_duration()
        except ValueError as e:  # pragma: no cover
            self._duration_label.setText(f"Error estimating time:\n{e}")
            return

        self._time_warning.setVisible(self._time_estimate.time_interval_exceeded)

        d = _format_duration(self._time_estimate.total_duration)
        d = f"Estimated duration: {d}" if d else ""
        self._duration_label.setText(d)

    def _simplify_af_offsets(self, seq: useq.MDASequence) -> dict:
        """If all positions have the same af offset, remove it from each position.

        Instead, add a global autofocus plan to the sequence.
        This function returns a dict of fields to update in the sequence.
        """
        if not seq.stage_positions:
            return {}

        # gather all the autofocus offsets in the subsequences
        af_offsets = {
            pos.sequence.autofocus_plan.autofocus_motor_offset
            for pos in seq.stage_positions
            if pos.sequence is not None and pos.sequence.autofocus_plan
        }

        # if they aren't all the same, there's nothing we can do to simplify it.
        if len(af_offsets) != 1:
            return {"stage_positions": self._update_af_axes(seq.stage_positions)}

        # otherwise, make a global AF plan and remove it from each position
        stage_positions = []
        for pos in seq.stage_positions:
            if pos.sequence and pos.sequence.autofocus_plan:
                # remove autofocus plan from the position
                pos = pos.replace(sequence=pos.sequence.replace(autofocus_plan=None))
                # after removing the autofocus plan, if the sequence is empty,
                # remove it altogether.
                if pos.sequence == NULL_SEQUENCE:
                    pos = pos.replace(sequence=None)
            stage_positions.append(pos)
        af_plan = useq.AxesBasedAF(
            autofocus_motor_offset=af_offsets.pop(), axes=self.af_axis.value()
        )
        return {"autofocus_plan": af_plan, "stage_positions": stage_positions}

    def _update_af_axes(
        self, positions: tuple[useq.Position, ...]
    ) -> tuple[useq.Position, ...]:
        """Add the autofocus axes to each subsequence."""
        new_pos = []
        for pos in positions:
            if (seq := pos.sequence) and (af_plan := seq.autofocus_plan):
                af_plan = af_plan.replace(axes=self.af_axis.value())
                pos = pos.replace(sequence=seq.replace(autofocus_plan=af_plan))
            new_pos.append(pos)

        return tuple(new_pos)
