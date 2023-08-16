from __future__ import annotations

from pathlib import Path
from typing import cast

import useq
from pint import Quantity
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._mda._checkable_tabwidget_widget import CheckableTabWidget
from pymmcore_widgets.useq_widgets._channels import ChannelTable
from pymmcore_widgets.useq_widgets._grid import GridPlanWidget
from pymmcore_widgets.useq_widgets._positions import PositionTable
from pymmcore_widgets.useq_widgets._time import TimeTable
from pymmcore_widgets.useq_widgets._z import ZPlanWidget


class MDATabs(CheckableTabWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.channels = ChannelTable(1)
        self.time_plan = TimeTable(1)
        self.z_plan = ZPlanWidget()
        self.stage_positions = PositionTable(1)
        self.grid_plan = GridPlanWidget()

        self.addTab(self.channels, "Channels", checked=False)
        self.addTab(self.time_plan, "Time", checked=False)
        self.addTab(self.z_plan, "Z Stack", checked=False)
        self.addTab(self.stage_positions, "Positions", checked=False)
        self.addTab(self.grid_plan, "Grid", checked=False)
        self.setCurrentIndex(0)

    def isAxisUsed(self, key: str | QWidget) -> bool:
        """Return True if the given axis is used in the sequence.

        Parameters
        ----------
        key : str | QWidget
            The axis to check. Can be one of "c", "t", "p", or "g", "z", or the
            corresponding widget instance (e.g. self.channels, etc...)
        """
        if isinstance(key, str):
            try:
                key = {
                    "c": self.channels,
                    "t": self.time_plan,
                    "p": self.stage_positions,
                    "z": self.z_plan,
                    "g": self.grid_plan,
                }[key[0].lower()]
            except KeyError as e:  # pragma: no cover
                raise ValueError(f"Invalid key: {key!r}") from e
        return bool(self.isChecked(key))

    def value(self) -> useq.MDASequence:
        """Return the current sequence as a `useq-schema` MDASequence."""
        return useq.MDASequence(
            z_plan=self.z_plan.value() if self.isAxisUsed("z") else None,
            time_plan=self.time_plan.value() if self.isAxisUsed("t") else None,
            stage_positions=self.stage_positions.value()
            if self.isAxisUsed("p")
            else (),
            channels=self.channels.value() if self.isAxisUsed("c") else (),
            grid_plan=self.grid_plan.value() if self.isAxisUsed("g") else None,
        )

    def setValue(self, value: useq.MDASequence) -> None:
        """Set widget value from a `useq-schema` MDASequence."""
        if not isinstance(value, useq.MDASequence):  # pragma: no cover
            raise TypeError(f"Expected useq.MDASequence, got {type(value)}")

        widget: ChannelTable | TimeTable | ZPlanWidget | PositionTable | GridPlanWidget
        for f in ("channels", "time_plan", "z_plan", "stage_positions", "grid_plan"):
            widget = getattr(self, f)
            if field_val := getattr(value, f):
                widget.setValue(field_val)
                self.setChecked(widget, True)
            else:
                # widget.setValue(None)
                self.setChecked(widget, False)


class MDASequenceWidget(QWidget):
    """Widget for editing a `useq-schema` MDA sequence."""

    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # -------------- Main MDA Axis Widgets --------------

        self.tab_wdg = MDATabs()
        self.channels = self.tab_wdg.channels
        self.time_plan = self.tab_wdg.time_plan
        self.z_plan = self.tab_wdg.z_plan
        self.stage_positions = self.tab_wdg.stage_positions
        self.grid_plan = self.tab_wdg.grid_plan

        # -------------- Other Widgets --------------

        # QLabel with standard warning icon to indicate time overflow
        style = self.style()
        warning_icon = style.standardIcon(style.StandardPixmap.SP_MessageBoxWarning)
        self._time_warning = QLabel()
        self._time_warning.setPixmap(warning_icon.pixmap(24, 24))
        self._time_warning.hide()
        self._duration_label = QLabel()
        self._duration_label.setWordWrap(True)

        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self.save)
        self._load_button = QPushButton("Load")
        self._load_button.clicked.connect(self.load)

        # -------------- Main Layout --------------

        bot_row = QHBoxLayout()
        bot_row.addWidget(self._time_warning)
        bot_row.addWidget(self._duration_label)
        bot_row.addStretch()
        bot_row.addWidget(self._save_button)
        bot_row.addWidget(self._load_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tab_wdg)
        layout.addLayout(bot_row)

        # -------------- Connections --------------

        self.channels.valueChanged.connect(self.valueChanged)
        self.time_plan.valueChanged.connect(self.valueChanged)
        self.stage_positions.valueChanged.connect(self.valueChanged)
        self.z_plan.valueChanged.connect(self.valueChanged)
        self.grid_plan.valueChanged.connect(self.valueChanged)
        self.tab_wdg.tabChecked.connect(self.valueChanged)
        self.valueChanged.connect(self._update_time_estimate)

    # -------------- Public API --------------

    def value(self) -> useq.MDASequence:
        """Return the current sequence as a `useq-schema` MDASequence."""
        return self.tab_wdg.value()

    def setValue(self, value: useq.MDASequence) -> None:
        """Set widget value from a `useq-schema` MDASequence."""
        self.tab_wdg.setValue(value)

    def save(self, file: str | Path | None = None) -> None:
        """Save the current sequence to a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getSaveFileName(
                self, "Save MDASequence and filename.", "", "json(*.json), yaml(*.yaml)"
            )
            if not file:  # pragma: no cover
                return

        dest = Path(file)
        if dest.suffix in {".yaml", ".yml"}:
            data = cast("str", self.value().yaml())
        elif dest.suffix == ".json":
            data = self.value().json()
        else:  # pragma: no cover
            raise ValueError(f"Invalid file extension: {dest.suffix!r}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(data)

    def load(self, file: str | Path | None = None) -> None:
        """Load sequence from a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getOpenFileName(
                self, "Select an MDAsequence file.", "", "json(*.json), yaml(*.yaml)"
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

    def _update_time_estimate(self) -> None:
        """Update the time estimate label."""
        val = self.value()
        try:
            self._time_estimate = val.estimate_duration()
        except ValueError as e:  # pragma: no cover
            self._duration_label.setText(f"Error estimating time:\n{e}")
            return

        self._time_warning.setVisible(self._time_estimate.time_interval_exceeded)

        d = Quantity(self._time_estimate.total_duration, "s").to_compact()
        self._duration_label.setText(f"Estimated duration: {d:.1f~#P}")


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = MDASequenceWidget()
    widget.valueChanged.connect(lambda: print(widget.value()))
    widget.show()
    sys.exit(app.exec_())