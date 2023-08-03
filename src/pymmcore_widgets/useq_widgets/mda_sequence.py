from __future__ import annotations

from qtpy.QtWidgets import QVBoxLayout, QWidget

from pymmcore_widgets._mda._checkable_tabwidget_widget import CheckableTabWidget

from .channels import ChannelTable
from .positions import PositionTable
from .time import TimeTable


class MDASequenceWidget(QWidget):
    """Widget for editing a `useq-schema` MDA sequence."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # main TabWidget

        self.channels = ChannelTable(1)
        self.time = TimeTable(1)
        self.positions = PositionTable(1)

        self._tab = CheckableTabWidget()
        self._tab.addTab(self.channels, "Channels")
        self._tab.addTab(self.time, "Time")
        self._tab.addTab(self.positions, "Positions")

        layout = QVBoxLayout(self)
        layout.addWidget(self._tab)
