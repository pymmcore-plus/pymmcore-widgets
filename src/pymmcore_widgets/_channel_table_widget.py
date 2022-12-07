from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
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
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).
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
        # TODO: we should also implement the other channel parameters
        # e.g. z_offset, do_stack, ...
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
        self.clear_ch_button.clicked.connect(self.clear_channel)

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
            warnings.warn("First select Micro-Manager 'ChannelGroup'.")
            return False

        channel_combobox = self._create_channel_combobox()
        if not channel_combobox:
            return False

        channel_exp_spinbox = self._create_exposure_doublespinbox()

        self._add_widgets_to_table(channel_combobox, channel_exp_spinbox)
        return True

    def _create_channel_combobox(self, channel_group: str = "") -> QComboBox | None:
        channel_combobox = QComboBox()

        ch_group = channel_group or self._mmc.getChannelGroup()
        if not ch_group:
            return None

        channel_list = list(self._mmc.getAvailableConfigs(ch_group))
        channel_combobox.addItems(channel_list)
        return channel_combobox

    def _create_exposure_doublespinbox(self) -> QDoubleSpinBox:
        channel_exp_spinbox = QDoubleSpinBox()
        channel_exp_spinbox.setRange(0, 10000)
        channel_exp_spinbox.setValue(100)
        channel_exp_spinbox.setAlignment(AlignCenter)
        channel_exp_spinbox.valueChanged.connect(self.valueChanged)
        return channel_exp_spinbox

    def _add_widgets_to_table(
        self, channel_combo: QComboBox, exp_dspinbox: QDoubleSpinBox
    ) -> None:
        idx = self.channel_tableWidget.rowCount()
        self.channel_tableWidget.insertRow(idx)
        self.channel_tableWidget.setCellWidget(idx, 0, channel_combo)
        self.channel_tableWidget.setCellWidget(idx, 1, exp_dspinbox)
        channel_combo.setCurrentIndex(self._get_new_channel_index())

        self.valueChanged.emit()

    def _get_new_channel_index(self) -> int:
        if self.channel_tableWidget.rowCount() == 1:
            return 0
        combo = self.channel_tableWidget.cellWidget(0, 0)
        items = [combo.itemText(i) for i in range(combo.count())]
        idxs = list(range(len(items)))
        used_idxs = []
        for row in range(self.channel_tableWidget.rowCount() - 1):
            combo = cast(QComboBox, self.channel_tableWidget.cellWidget(row, 0))
            used_idxs.append(combo.currentIndex())
        new_idxs = list(set(idxs) - set(used_idxs))

        print(idxs, used_idxs)
        print(new_idxs)

        return new_idxs[0] if new_idxs else 0

    def _remove_channel(self) -> None:
        rows = {r.row() for r in self.channel_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.channel_tableWidget.removeRow(idx)
        self.valueChanged.emit()

    def clear_channel(self) -> None:
        """Clear the channel table."""
        self.channel_tableWidget.clearContents()
        self.channel_tableWidget.setRowCount(0)
        self.valueChanged.emit()

    def value(self) -> list[ChannelDict]:
        """Return the current channels settings.

        Note that output dict will match the Channel from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel>
        """
        return [
            {
                "config": self.channel_tableWidget.cellWidget(c, 0).currentText(),
                "group": self._mmc.getChannelGroup() or "Channel",
                "exposure": self.channel_tableWidget.cellWidget(c, 1).value(),
            }
            for c in range(self.channel_tableWidget.rowCount())
        ]

    def set_state(self, channels: list[ChannelDict] | list[dict[str, Any]]) -> None:
        """Set the state of the widget from a useq channel dictionary."""
        self.clear_channel()

        for channel in channels:
            if "config" not in channel:
                raise ValueError("Dictionary should contain channel 'config' name.")

            ch_group = channel.get("group") or ""
            channel_combobox = self._create_channel_combobox(ch_group)
            if not channel_combobox:
                warnings.warn("ChannelGroup is not defined!")
                continue

            ch = channel.get("config")
            if ch in self._mmc.getAvailableConfigs(self._mmc.getChannelGroup()):
                channel_combobox.setCurrentText(ch)
            else:
                warnings.warn(
                    f"'{ch}' config or its group doesn't exist in the "
                    f"'{self._mmc.getChannelGroup()}' ChannelGroup!"
                )
                continue

            channel_exp_spinbox = self._create_exposure_doublespinbox()
            channel_exp_spinbox.setValue(
                channel.get("exposure") or self._mmc.getExposure()
            )

            self._add_widgets_to_table(channel_combobox, channel_exp_spinbox)
