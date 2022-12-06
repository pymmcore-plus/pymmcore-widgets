from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class ChannelDict(TypedDict):
        """Channel dictionary."""

        config: str
        group: str
        exposure: float


AlignCenter = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


class ChannelTable(QGroupBox):
    """Widget providing options for setting up a multi-channel acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Channel
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#Channel).
    """

    valueChanged = Signal()

    def __init__(
        self,
        title: str = "Channels",
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(title, parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # channel table
        self.channel_tableWidget = QTableWidget()
        hdr = self.channel_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self.channel_tableWidget.verticalHeader().setVisible(False)
        self.channel_tableWidget.setTabKeyNavigation(True)
        self.channel_tableWidget.setColumnCount(2)
        self.channel_tableWidget.setRowCount(0)
        self.channel_tableWidget.setHorizontalHeaderLabels(["Channel", "Exposure (ms)"])
        group_layout.addWidget(self.channel_tableWidget, 0, 0)

        # buttons
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        min_size = 100
        self.add_ch_button = QPushButton(text="Add")
        self.add_ch_button.setMinimumWidth(min_size)
        self.add_ch_button.setSizePolicy(btn_sizepolicy)
        self.remove_ch_button = QPushButton(text="Remove")
        self.remove_ch_button.setMinimumWidth(min_size)
        self.remove_ch_button.setSizePolicy(btn_sizepolicy)
        self.clear_ch_button = QPushButton(text="Clear")
        self.clear_ch_button.setMinimumWidth(min_size)
        self.clear_ch_button.setSizePolicy(btn_sizepolicy)

        self.add_ch_button.clicked.connect(self._add_channel)
        self.remove_ch_button.clicked.connect(self._remove_channel)
        self.clear_ch_button.clicked.connect(self._clear_channel)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_ch_button)
        layout.addWidget(self.remove_ch_button)
        layout.addWidget(self.clear_ch_button)
        layout.addItem(spacer)

        group_layout.addWidget(wdg, 0, 1)

    def _add_channel(self) -> bool:
        """Add, remove or clear channel table.  Return True if anyting was changed."""
        if len(self._mmc.getLoadedDevices()) <= 1:
            return False

        channel_group = self._mmc.getChannelGroup()
        if not channel_group:
            return False

        idx = self.channel_tableWidget.rowCount()
        self.channel_tableWidget.insertRow(idx)

        channel_combobox = QComboBox(self)
        if channel_group := self._mmc.getChannelGroup():
            channel_list = list(self._mmc.getAvailableConfigs(channel_group))
            channel_combobox.addItems(channel_list)

        channel_exp_spinbox = QSpinBox(self)
        channel_exp_spinbox.setRange(0, 10000)
        channel_exp_spinbox.setValue(100)
        channel_exp_spinbox.setAlignment(AlignCenter)
        channel_exp_spinbox.valueChanged.connect(self.valueChanged)

        self.channel_tableWidget.setCellWidget(idx, 0, channel_combobox)
        self.channel_tableWidget.setCellWidget(idx, 1, channel_exp_spinbox)

        self.valueChanged.emit()

        return True

    def _remove_channel(self) -> None:
        rows = {r.row() for r in self.channel_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.channel_tableWidget.removeRow(idx)
        self.valueChanged.emit()

    def _clear_channel(self) -> None:
        self.channel_tableWidget.clearContents()
        self.channel_tableWidget.setRowCount(0)
        self.valueChanged.emit()

    def value(self) -> list[ChannelDict]:
        """Return the current channels settings.

        Note that output dict will match the Channel from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#Channel>
        """
        return [
            {
                "config": self.channel_tableWidget.cellWidget(c, 0).currentText(),
                "group": self._mmc.getChannelGroup() or "Channel",
                "exposure": self.channel_tableWidget.cellWidget(c, 1).value(),
            }
            for c in range(self.channel_tableWidget.rowCount())
        ]

    def set_state(self, channels: dict) -> None:
        """Set the state of the widget from a useq channel dictionary."""
        pass


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()
    app = QApplication(sys.argv)
    win = ChannelTable(mmcore=mmc)
    win.show()
    sys.exit(app.exec_())
