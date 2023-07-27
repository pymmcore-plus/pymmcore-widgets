from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from superqt import fonticon
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


class ChannelTable(QWidget):
    """Widget providing options for setting up a multi-channel acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Channel
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    channel_group : str | None
        Optional channel group that will be set as the widget's initial ChannelGroup.
        By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    valueChanged = Signal()
    CH_GROUP_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        channel_group: str | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

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
        self._table.setColumnCount(5)
        self._table.setRowCount(0)
        self._table.setHorizontalHeaderLabels(
            ["Channel", "Exposure (ms)", "Z offset", "Z stack", "Acquire Every"]
        )
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

        self._add_button = QPushButton(text="Add")
        self._remove_button = QPushButton(text="Remove")
        self._clear_button = QPushButton(text="Clear")

        self._add_button.clicked.connect(self._create_new_row)
        self._remove_button.clicked.connect(self._remove_selected_rows)
        self._clear_button.clicked.connect(self.clear)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        advanced_wdg = QWidget()
        advanced_wdg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        advanced_layout = QHBoxLayout()
        advanced_layout.setSpacing(5)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_wdg.setLayout(advanced_layout)
        self._advanced_cbox = QCheckBox("Advanced")
        self._advanced_cbox.toggled.connect(self._on_advanced_toggled)
        self._warn_icon = QLabel()
        self._warn_icon.setToolTip("Warning: some 'Advanced' values are selected!")
        _icon = fonticon.icon(MDI6.alert_outline, color="magenta")
        self._warn_icon.setPixmap(_icon.pixmap(QSize(25, 25)))
        advanced_layout.addWidget(self._advanced_cbox)
        advanced_layout.addWidget(self._warn_icon)
        _w = (
            self._advanced_cbox.sizeHint().width()
            + self._warn_icon.sizeHint().width()
            + advanced_layout.spacing()
        )
        advanced_wdg.setMinimumWidth(_w)
        advanced_wdg.setMinimumHeight(advanced_wdg.sizeHint().height())
        self._warn_icon.hide()

        self._add_button.setMinimumWidth(_w)
        self._remove_button.setMinimumWidth(_w)
        self._clear_button.setMinimumWidth(_w)

        layout.addWidget(self._add_button)
        layout.addWidget(self._remove_button)
        layout.addWidget(self._clear_button)
        layout.addWidget(advanced_wdg)
        layout.addItem(spacer)

        group_layout.addWidget(wdg, 0, 1)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.configGroupDeleted.connect(self._on_group_deleted)
        self._mmc.events.configDeleted.connect(self._on_config_deleted)

        self.destroyed.connect(self._disconnect)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self.clear()
        self._advanced_cbox.setChecked(False)
        self._on_advanced_toggled(False)

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
            items_data = {
                combo.itemData(ch, self.CH_GROUP_ROLE) for ch in range(combo.count())
            }
            if group in items_data and config in items:
                combo.clear()
                combo.addItems(self._mmc.getAvailableConfigs(group))
                for i in range(combo.count()):
                    combo.setItemData(i, group, self.CH_GROUP_ROLE)
                if self._mmc.getChannelGroup() != config:
                    combo.setCurrentText(self._mmc.getChannelGroup())

    def _on_advanced_toggled(self, state: bool) -> None:
        for c in range(2, self._table.columnCount()):
            self._table.setColumnHidden(c, not state)

        if not state:
            for v in self.value():
                # if any of the advanced settings are different from their default
                if v["z_offset"] != 0 or not v["do_stack"] or v["acquire_every"] != 1:
                    self._warn_icon.show()
                    return
        self._warn_icon.hide()

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

    def _create_spinbox(
        self, range: tuple[int, int], double: bool = False
    ) -> QDoubleSpinBox:
        dspinbox = QDoubleSpinBox() if double else QSpinBox()
        dspinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        dspinbox.setRange(*range)
        dspinbox.setAlignment(Qt.AlignCenter)
        dspinbox.wheelEvent = lambda event: None  # block mouse scroll
        dspinbox.setKeyboardTracking(False)
        dspinbox.valueChanged.connect(self.valueChanged)
        return dspinbox

    def _create_new_row(
        self,
        channel: str | None = None,
        exposure: float | None = None,
        channel_group: str | None = None,
        z_offset: float = 0.0,
        do_stack: bool = True,
        acquire_every: int = 1,
    ) -> None:
        """Create a new row in the table.

        If 'channel' is not provided, the first unused channel will be used.
        If 'exposure' is not provided, the current exposure will be used (or 100).
        """
        if len(self._mmc.getLoadedDevices()) <= 1:
            warnings.warn("No devices loaded.", stacklevel=2)
            return

        _channel_group = channel_group or self.channel_group_combo.currentText()

        if not _channel_group:
            warnings.warn("First select Micro-Manager 'ChannelGroup'.", stacklevel=2)
            return

        # channel dropdown
        channel_combo = QComboBox()
        available = self._mmc.getAvailableConfigs(_channel_group)
        channel = channel or self._pick_first_unused_channel(available)
        channel_combo.addItems(available)
        for i in range(channel_combo.count()):
            channel_combo.setItemData(i, _channel_group, self.CH_GROUP_ROLE)
        channel_combo.setCurrentText(channel)

        # exposure spinbox
        channel_exp_spinbox = self._create_spinbox((0, 10000), True)
        channel_exp_spinbox.setMinimum(1)
        channel_exp_spinbox.setValue(exposure or self._mmc.getExposure() or 100)

        # z offset spinbox
        z_offset_spinbox = self._create_spinbox((-10000, 10000), True)
        z_offset_spinbox.setValue(z_offset)

        # z stack checkbox
        # creating a wrapper widget so that the checkbox appears centered.
        z_stack_wdg = QWidget()
        z_stack_layout = QHBoxLayout()
        z_stack_layout.setContentsMargins(0, 0, 0, 0)
        z_stack_layout.setAlignment(Qt.AlignCenter)
        z_stack_wdg.setLayout(z_stack_layout)
        z_stack_checkbox = QCheckBox()
        z_stack_checkbox.setChecked(do_stack)
        z_stack_checkbox.stateChanged.connect(self.valueChanged)
        z_stack_layout.addWidget(z_stack_checkbox)

        # acqire every spinbox
        acquire_every_spinbox = self._create_spinbox((1, 10000))
        acquire_every_spinbox.setValue(acquire_every)

        idx = self._table.rowCount()
        self._table.insertRow(idx)
        self._table.setCellWidget(idx, 0, channel_combo)
        self._table.setCellWidget(idx, 1, channel_exp_spinbox)
        self._table.setCellWidget(idx, 2, z_offset_spinbox)
        self._table.setCellWidget(idx, 3, z_stack_wdg)
        self._table.setCellWidget(idx, 4, acquire_every_spinbox)
        self.valueChanged.emit()

    def _z_stack_checkbox(self, row: int) -> QCheckBox:
        return self._table.cellWidget(row, 3).layout().itemAt(0).widget()

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
        """Return the current channels settings as a list of dictionaries.

        Note that the output will match the [useq-schema Channel
        specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).
        """
        values: list[ChannelDict] = []
        for c in range(self._table.rowCount()):
            name_widget = cast("QComboBox", self._table.cellWidget(c, 0))
            exposure_widget = cast("QDoubleSpinBox", self._table.cellWidget(c, 1))
            if name_widget and exposure_widget:
                values.append(
                    {
                        "config": name_widget.currentText(),
                        "group": name_widget.itemData(
                            name_widget.currentIndex(), self.CH_GROUP_ROLE
                        ),
                        "exposure": exposure_widget.value(),
                        # NOTE: the columns representing these values *may* be hidden
                        # ... but we are still using them
                        "z_offset": (
                            cast("QDoubleSpinBox", self._table.cellWidget(c, 2)).value()
                        ),
                        "do_stack": (self._z_stack_checkbox(c).isChecked()),
                        "acquire_every": (
                            cast("QSpinBox", self._table.cellWidget(c, 4)).value()
                        ),
                    }
                )
        return values

    # note: this really ought to be ChannelDict, but it makes typing elsewhere harder
    # TODO: also accept actual useq objects
    def set_state(self, channels: list[dict]) -> None:
        """Set the state of the widget.

        Parameters
        ----------
        channels : list[dict]
            A list of dictionaries following the [useq-schema Channel specifications](
            https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).
        """
        _advanced_bool = False
        with signals_blocked(self):
            self.clear()
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
                        f"'{group}' ChannelGroup!",
                        stacklevel=2,
                    )
                    continue

                exposure = channel.get("exposure") or self._mmc.getExposure()
                z_offset = channel.get("z_offset") or 0.0
                do_stack = channel["do_stack"] if "do_stack" in channel else True
                acquire_every = channel.get("acquire_every") or 1
                self._create_new_row(
                    ch, exposure, group, z_offset, do_stack, acquire_every
                )

                # if any of the advanced settings are different from their default
                if z_offset != 0.0 or not do_stack or acquire_every != 1:
                    _advanced_bool = True

            self._advanced_cbox.setChecked(_advanced_bool)

        self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
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
