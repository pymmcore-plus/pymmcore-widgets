from __future__ import annotations

from itertools import permutations
from pathlib import Path
from typing import cast

import useq
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
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
from pymmcore_widgets._mda._checkable_tabwidget_widget import CheckableTabWidget
from pymmcore_widgets.useq_widgets._channels import ChannelTable
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


AXES = "tpgcz"
ALLOWED_ORDERS = {"".join(p) for x in range(1, 6) for p in permutations(AXES, x)}
for x in list(ALLOWED_ORDERS):
    for first, second in (
        ("t", "c"),  # t cannot come after c
        ("t", "z"),  # t cannot come after z
        ("p", "g"),  # p cannot come after g
        ("p", "c"),  # p cannot come after c
        ("p", "z"),  # p cannot come after z
        ("g", "z"),  # g cannot come after z
    ):
        if _check_order(x, first, second):
            ALLOWED_ORDERS.discard(x)


class MDATabs(CheckableTabWidget):
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
            The axis to check. Can be one of "c", "t", "p", or "g", "z", or the
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
        """Return the current sequence as a `useq-schema` MDASequence."""
        return useq.MDASequence(
            z_plan=self.z_plan.value() if self.isAxisUsed("z") else None,
            time_plan=self.time_plan.value() if self.isAxisUsed("t") else None,
            stage_positions=(
                self.stage_positions.value() if self.isAxisUsed("p") else ()
            ),
            channels=self.channels.value() if self.isAxisUsed("c") else (),
            grid_plan=self.grid_plan.value() if self.isAxisUsed("g") else None,
            metadata={"pymmcore_widgets": {"version": pymmcore_widgets.__version__}},
        )

    def setValue(self, value: useq.MDASequence) -> None:
        """Set widget value from a `useq-schema` MDASequence."""
        if not isinstance(value, useq.MDASequence):  # pragma: no cover
            raise TypeError(f"Expected useq.MDASequence, got {type(value)}")

        widget: ChannelTable | TimePlanWidget | ZPlanWidget | PositionTable | GridPlanWidget  # noqa
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


class MDASequenceWidget(QWidget):
    """Widget for editing a `useq-schema` MDA sequence."""

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

        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self.save)
        self._load_button = QPushButton("Load")
        self._load_button.clicked.connect(self.load)

        # -------------- Main Layout --------------

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Axis Order:"))
        top_row.addWidget(self.axis_order)
        top_row.addStretch()

        bot_row = QHBoxLayout()
        bot_row.addWidget(self._time_warning)
        bot_row.addWidget(self._duration_label)
        bot_row.addWidget(self._save_button)
        bot_row.addWidget(self._load_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.tab_wdg)
        layout.addLayout(bot_row)

        # -------------- Connections --------------

        self.channels.valueChanged.connect(self.valueChanged)
        self.time_plan.valueChanged.connect(self.valueChanged)
        self.stage_positions.valueChanged.connect(self.valueChanged)
        self.z_plan.valueChanged.connect(self.valueChanged)
        self.grid_plan.valueChanged.connect(self.valueChanged)
        self.tab_wdg.tabChecked.connect(self._on_tab_checked)
        self.axis_order.currentTextChanged.connect(self.valueChanged)
        self.valueChanged.connect(self._update_time_estimate)

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
        """Return the current sequence as a `useq-schema` MDASequence."""
        val = self.tab_wdg.value()
        shutters: tuple[str, ...] = ()
        if self.z_plan.leave_shutter_open.isChecked():
            shutters += ("z",)
        if self.time_plan.leave_shutter_open.isChecked():
            shutters += ("t",)
        return val.replace(
            axis_order=self.axis_order.currentText(), keep_shutter_open_across=shutters
        )

    def setValue(self, value: useq.MDASequence) -> None:
        """Set widget value from a `useq-schema` MDASequence."""
        self.tab_wdg.setValue(value)
        self.axis_order.setCurrentText("".join(value.axis_order))

        keep_shutter_open = value.keep_shutter_open_across
        self.z_plan.leave_shutter_open.setChecked("z" in keep_shutter_open)
        self.time_plan.leave_shutter_open.setChecked("t" in keep_shutter_open)

    def save(self, file: str | Path | None = None) -> None:
        """Save the current sequence to a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getSaveFileName(
                self,
                "Save MDASequence and filename.",
                "",
                "All (*.yaml *yml *json);;YAML (*.yaml *.yml);;JSON (*.json)",
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
            data = self.value().json(exclude_unset=True, exclude_defaults=True)
        else:  # pragma: no cover
            raise ValueError(f"Invalid file extension: {dest.suffix!r}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(data)

    def load(self, file: str | Path | None = None) -> None:
        """Load sequence from a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getOpenFileName(
                self,
                "Select an MDAsequence file.",
                "",
                "All (*.yaml *yml *json);;YAML (*.yaml *.yml);;JSON (*.json)",
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

    def _on_tab_checked(self, idx: int, checked: bool) -> None:
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
