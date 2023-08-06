from __future__ import annotations

import useq
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QVBoxLayout, QWidget

from pymmcore_widgets._mda._checkable_tabwidget_widget import CheckableTabWidget
from pymmcore_widgets.useq_widgets._channels import ChannelTable
from pymmcore_widgets.useq_widgets._grid import GridPlanWidget
from pymmcore_widgets.useq_widgets._positions import PositionTable
from pymmcore_widgets.useq_widgets._time import TimeTable
from pymmcore_widgets.useq_widgets._z import ZPlanWidget


class MDASequenceWidget(QWidget):
    """Widget for editing a `useq-schema` MDA sequence."""

    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # main TabWidget

        self.channels = ChannelTable(1)
        self.time = TimeTable(1)
        self.positions = PositionTable(1)
        self.z = ZPlanWidget()
        self.grid = GridPlanWidget()

        self._tab_wdg = CheckableTabWidget()
        self._tab_wdg.addTab(self.channels, "Channels", checked=False)
        self._tab_wdg.addTab(self.time, "Time", checked=False)
        self._tab_wdg.addTab(self.positions, "Positions", checked=False)
        self._tab_wdg.addTab(self.z, "Z", checked=False)
        self._tab_wdg.addTab(self.grid, "Grid", checked=False)

        self.channels.valueChanged.connect(self.valueChanged)
        self.time.valueChanged.connect(self.valueChanged)
        self.positions.valueChanged.connect(self.valueChanged)
        self.z.valueChanged.connect(self.valueChanged)
        self.grid.valueChanged.connect(self.valueChanged)
        self._tab_wdg.tabChecked.connect(self.valueChanged)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tab_wdg)

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
                    "t": self.time,
                    "p": self.positions,
                    "z": self.z,
                    "g": self.grid,
                }[key[0].lower()]
            except KeyError as e:
                raise ValueError(f"Invalid key: {key!r}") from e
        return bool(self._tab_wdg.isChecked(key))

    def value(self) -> useq.MDASequence:
        """Return the current sequence as a `useq-schema` MDASequence."""
        return useq.MDASequence(
            z_plan=self.z.value() if self.isAxisUsed("z") else None,
            time_plan=self.time.value() if self.isAxisUsed("t") else None,
            stage_positions=self.positions.value() if self.isAxisUsed("p") else (),
            channels=self.channels.value() if self.isAxisUsed("c") else (),
            grid_plan=self.grid.value() if self.isAxisUsed("g") else None,
        )


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = MDASequenceWidget()
    widget.valueChanged.connect(lambda: print(widget.value()))
    widget.show()
    sys.exit(app.exec_())
