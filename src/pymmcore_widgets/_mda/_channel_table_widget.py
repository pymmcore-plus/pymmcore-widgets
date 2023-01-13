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


class ChannelTable(QGroupBox):
    """Widget providing options for setting up a multi-channel acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Channel
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).

    Parameters
    ----------
    title : str
        Title of the QGroupBox widget. Bt default, 'Channel'.
    parent : QWidget | None
        Optional parent widget. By default, None.
    channel_group : str | None
        Optional channel group that will be set as the widget's initial
        ChannelGroup. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    valueChanged = Signal()
    CH_GROUP_ROLE = 1

    def __init__(
        self,
        title: str = "Channels",
        parent: QWidget | None = None,
        *,
        channel_group: str | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(title, parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # channel table
        self._table = QTableWidget()
        self._table.setMinimumHeight(175)
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

        # ChannelGroup combobox
        self.channel_group_combo = ChannelGroupCombo(
            self, channel_group=channel_group, mmcore=self._mmc
        )
        layout.addWidget(self.channel_group_combo)

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

        self._mmc.events.systemConfigurationLoaded.connect(self.clear)
        self._mmc.events.configGroupDeleted.connect(self._on_group_deleted)
        self._mmc.events.configDeleted.connect(self._on_config_deleted)

        self.destroyed.connect(self._disconnect)

    def _on_group_deleted(self, group: str) -> None:
        """Remove rows that are using channels from the deleted group."""
        row = 0
        for ch in self.value():
            if ch["group"] == group:
                self._table.removeRow(row)
            else:
                row += 1

    def _on_config_deleted(self, group: str, config: str) -> None:
        """Remove deleted config from channel combo if present."""
        for row in range(self._table.rowCount()):
            combo = cast(QComboBox, self._table.cellWidget(row, 0))
            items = [combo.itemText(ch) for ch in range(combo.count())]
            # channel_combo.setItemData(self.CH_GROUP_ROLE, _channel_group)
            if group == combo.itemData(self.CH_GROUP_ROLE) and config in items:
                # if group == combo.whatsThis() and config in items:
                combo.clear()
                combo.addItems(self._mmc.getAvailableConfigs(group))
                if self._mmc.getChannelGroup() != config:
                    combo.setCurrentText(self._mmc.getChannelGroup())

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

    def _create_new_row(
        self,
        channel: str | None = None,
        exposure: float | None = None,
        channel_group: str | None = None,
    ) -> None:
        """Create a new row in the table.

        If 'channel' is not provided, the first unused channel will be used.
        If 'exposure' is not provided, the current exposure will be used (or 100).
        """
        if len(self._mmc.getLoadedDevices()) <= 1:
            warnings.warn("No devices loaded.")
            return

        _channel_group = channel_group or self.channel_group_combo.currentText()

        if not _channel_group:
            warnings.warn("First select Micro-Manager 'ChannelGroup'.")
            return

        # channel dropdown
        channel_combo = QComboBox()
        # channel_combo.setWhatsThis(_channel_group)
        available = self._mmc.getAvailableConfigs(_channel_group)
        channel = channel or self._pick_first_unused_channel(available)
        channel_combo.addItems(available)
        channel_combo.setItemData(self.CH_GROUP_ROLE, _channel_group)
        channel_combo.setCurrentText(channel)

        # exposure spinbox
        channel_exp_spinbox = QDoubleSpinBox()
        channel_exp_spinbox.setRange(0, 10000)
        channel_exp_spinbox.setValue(exposure or self._mmc.getExposure() or 100)
        channel_exp_spinbox.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        channel_exp_spinbox.valueChanged.connect(self.valueChanged)

        idx = self._table.rowCount()
        self._table.insertRow(idx)
        self._table.setCellWidget(idx, 0, channel_combo)
        self._table.setCellWidget(idx, 1, channel_exp_spinbox)
        self.valueChanged.emit()

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
                        # "group": name_widget.whatsThis(),
                        "group": name_widget.itemData(self.CH_GROUP_ROLE),
                        "exposure": exposure_widget.value(),
                    }
                )
        return values

    # note: this really ought to be ChannelDict, but it makes typing elsewhere harder
    # TODO: also accept actual useq objects
    def set_state(self, channels: list[dict]) -> None:
        """Set the state of the widget from a useq channel dictionary."""
        self.clear()
        with signals_blocked(self):
            for channel in channels:
                ch = channel.get("config")
                group = channel.get("group")

                if not ch:
                    raise ValueError("Dictionary should contain channel 'config' name.")
                avail_configs = self._mmc.getAvailableConfigs(
                    group or self.channel_group_combo.currentText()
                )
                if ch not in avail_configs:
                    warnings.warn(
                        f"'{ch}' config or its group doesn't exist in the "
                        f"'{group}' ChannelGroup!"
                    )
                    continue

                exposure = channel.get("exposure") or self._mmc.getExposure()
                self._create_new_row(ch, exposure, group)

        self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self.clear)
        self._mmc.events.configGroupDeleted.disconnect(self._on_group_deleted)
        self._mmc.events.configDeleted.disconnect(self._on_config_deleted)


class ChannelGroupCombo(QComboBox):
    """QComboBox to set the channel group to use in the ChannelTable."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        channel_group: str | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)

        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._channel_group = channel_group or self._mmc.getChannelGroup()

        # connect core
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.configGroupDeleted.connect(self._update_channel_group_combo)
        self._mmc.events.configDefined.connect(self._update_channel_group_combo)

        self.destroyed.connect(self._disconnect)

        self._update_channel_group_combo()

        self.currentTextChanged.connect(self._on_text_changed)

    def _on_sys_cfg_loaded(self) -> None:
        if not self._channel_group:
            self._channel_group = self._mmc.getChannelGroup()
        self._update_channel_group_combo()

    def _update_channel_group_combo(self) -> None:
        if len(self._mmc.getLoadedDevices()) <= 1:
            return
        with signals_blocked(self):
            self.clear()
            groups = self._mmc.getAvailableConfigGroups()
            self.addItems(groups)
            self.adjustSize()

        if not self._channel_group or self._channel_group not in groups:
            self._channel_group = self.currentText()
            return

        self.setCurrentText(self._channel_group)

    def _on_text_changed(self, group: str) -> None:
        if group != self._channel_group:
            self._channel_group = group

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.configGroupDeleted.disconnect(self._update_channel_group_combo)
        self._mmc.events.configDefined.disconnect(self._update_channel_group_combo)
