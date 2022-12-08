from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, cast

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
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from typing_extensions import Required, TypedDict

    class ChannelDict(TypedDict, total=False):
        """Channel dictionary."""

        config: Required[str]
        group: str
        exposure: float | None
        z_offset: float
        do_stack: bool
        camera: str | None
        acquire_every: int


AlignCenter = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


class ChannelTable(QGroupBox):
    """Widget providing options for setting up a multi-channel acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Channel
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).
    """

    valueChanged = Signal()
    _channel_group: str

    def __init__(
        self,
        title: str = "Channels",
        parent: QWidget | None = None,
        *,
        channel_group: str = "",
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(title, parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self.setChannelGroup(channel_group or self._mmc.getChannelGroup())

        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # channel table
        self._table = QTableWidget()
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setTabKeyNavigation(True)
        self._table.setColumnCount(2)
        self._table.setRowCount(0)
        # TODO: we should also implement the other channel parameters
        # e.g. z_offset, do_stack, ...
        self._table.setHorizontalHeaderLabels(["Channel", "Exposure (ms)"])
        group_layout.addWidget(self._table, 0, 0)

        # buttons
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        min_size = 100
        self._add_button = QPushButton(text="Add")
        self._add_button.setMinimumWidth(min_size)
        self._remove_button = QPushButton(text="Remove")
        self._remove_button.setMinimumWidth(min_size)
        self._clear_button = QPushButton(text="Clear")
        self._clear_button.setMinimumWidth(min_size)

        self._add_button.clicked.connect(self._create_new_row)
        self._remove_button.clicked.connect(self._remove_selected_rows)
        self._clear_button.clicked.connect(self.clear)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self._add_button)
        layout.addWidget(self._remove_button)
        layout.addWidget(self._clear_button)
        layout.addItem(spacer)

        group_layout.addWidget(wdg, 0, 1)

    def setChannelGroup(self, group: str) -> None:
        """Set current channel group."""
        if group:
            avail = self._mmc.getAvailableConfigGroups()
            if group not in avail:
                raise ValueError(
                    f"ChannelGroup '{group}' not available config groups: {avail!r}."
                )
        self._channel_group = group

    def channelGroup(self) -> str:
        """Return current channel group."""
        return self._channel_group

    def _create_new_row(
        self, channel: str | None = None, exposure: float | None = None
    ) -> None:
        """Create a new row in the table.

        If 'channel' is not provided, the first unused channel will be used.
        If 'exposure' is not provided, the current exposure will be used (or 100).
        """
        if len(self._mmc.getLoadedDevices()) <= 1:
            warnings.warn("No devices loaded.")
            return

        if not self._channel_group:
            warnings.warn("First select Micro-Manager 'ChannelGroup'.")
            return

        # channel dropdown
        channel_combo = QComboBox()
        available = self._mmc.getAvailableConfigs(self._channel_group)
        channel = channel or self._pick_first_unused_channel(available)
        channel_combo.addItems(available)
        channel_combo.setCurrentText(channel)

        # exposure spinbox
        channel_exp_spinbox = QDoubleSpinBox()
        channel_exp_spinbox.setRange(0, 10000)
        channel_exp_spinbox.setValue(exposure or self._mmc.getExposure() or 100)
        channel_exp_spinbox.setAlignment(AlignCenter)
        channel_exp_spinbox.valueChanged.connect(self.valueChanged)

        idx = self._table.rowCount()
        self._table.insertRow(idx)
        self._table.setCellWidget(idx, 0, channel_combo)
        self._table.setCellWidget(idx, 1, channel_exp_spinbox)
        self.valueChanged.emit()

    def _pick_first_unused_channel(self, available: tuple[str, ...]) -> str:
        """Return index of first unused channel."""
        used = set()
        for row in range(self._table.rowCount()):
            combo = cast(QComboBox, self._table.cellWidget(row, 0))
            used.add(combo.currentText())

        for ch in available:
            if ch not in used:
                return ch
        return available[0]

    def _remove_selected_rows(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        if not rows:
            return
        for idx in sorted(rows, reverse=True):
            self._table.removeRow(idx)
        self.valueChanged.emit()

    def clear(self) -> None:
        """Clear the channel table."""
        if self._table.rowCount():
            self._table.clearContents()
            self._table.setRowCount(0)
            self.valueChanged.emit()

    def value(self) -> list[ChannelDict]:
        """Return the current channels settings.

        Note that output dict will match the Channel from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel>
        """
        values: list[ChannelDict] = []
        for c in range(self._table.rowCount()):
            name_widget = cast(QComboBox, self._table.cellWidget(c, 0))
            exposure_widget = cast(QDoubleSpinBox, self._table.cellWidget(c, 1))
            if name_widget and exposure_widget:
                values.append(
                    {
                        "config": name_widget.currentText(),
                        "group": self._mmc.getChannelGroup() or "Channel",
                        "exposure": exposure_widget.value(),
                    }
                )
        return values

    # note: this really ought to be ChannelDict, but it makes typing elsewhere harder
    # TODO: also accept actual useq objects
    def set_state(self, channels: list[dict]) -> None:
        """Set the state of the widget from a useq channel dictionary."""
        groups: set[str] = {c["group"] for c in channels if c.get("group")}
        if len(groups) > 1:
            raise ValueError("All channels should be in the same group.")
        elif len(groups) == 1:
            self.setChannelGroup(groups.pop())

        avail_configs = set(self._mmc.getAvailableConfigs(self._mmc.getChannelGroup()))

        self.clear()
        with signals_blocked(self):
            for channel in channels:
                ch = channel.get("config")
                if not ch:
                    raise ValueError("Dictionary should contain channel 'config' name.")
                if ch not in avail_configs:
                    warnings.warn(
                        f"'{ch}' config or its group doesn't exist in the "
                        f"'{self._mmc.getChannelGroup()}' ChannelGroup!"
                    )
                    continue

                exposure = channel.get("exposure") or self._mmc.getExposure()
                self._create_new_row(ch, exposure)

        self.valueChanged.emit()
