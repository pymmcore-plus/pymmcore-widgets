from __future__ import annotations

from collections.abc import Iterable
from logging import getLogger
from re import Pattern
from typing import TYPE_CHECKING, Callable, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty, DeviceType
from pymmcore_plus.model import Setting
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QAbstractScrollArea, QTableWidget, QTableWidgetItem, QWidget
from superqt.iconify import QIconifyIcon
from superqt.utils import signals_blocked

from pymmcore_widgets._icons import DEVICE_TYPE_ICON
from pymmcore_widgets._util import NoWheelTableWidget

from ._property_widget import PropertyWidget

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = getLogger(__name__)


class DevicePropertyTable(NoWheelTableWidget):
    """Table of all currently loaded device properties.

    This table is used by `PropertyBrowser` to display all properties in the system,
    and by the `GroupPresetTableWidget`.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget, by default None
    enable_property_widgets : bool, optional
        Whether to enable each property widget, by default True
    mmcore : CMMCorePlus, optional
        CMMCore instance, by default None
    connect_core : bool, optional
        Whether to connect the widget to the core. If False, changes in the table
        will not update the core. By default, True.
    """

    valueChanged = Signal()
    PROP_ROLE = QTableWidgetItem.ItemType.UserType + 1

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        enable_property_widgets: bool = True,
        mmcore: CMMCorePlus | None = None,
        connect_core: bool = True,
    ):
        rows = 0
        cols = 2
        super().__init__(rows, cols, parent)

        self._rows_checkable: bool = False
        self._prop_widgets_enabled: bool = enable_property_widgets
        self._connect_core = connect_core

        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._rebuild_table)

        self.itemChanged.connect(self._on_item_changed)
        # If we enable these, then the edit group dialog will lose all of it's checks
        # whenever modify group button is clicked.  However, We don't want this widget
        # to have to be aware of a current group (or do we?)
        # self._mmc.events.configGroupDeleted.connect(self._rebuild_table)
        # self._mmc.events.configDeleted.connect(self._rebuild_table)
        # self._mmc.events.configDefined.connect(self._rebuild_table)

        self.destroyed.connect(self._disconnect)

        self.setMinimumWidth(500)
        self.setHorizontalHeaderLabels(["Device-Property", "Value"])
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.horizontalHeader().setStretchLastSection(True)

        vh = self.verticalHeader()
        vh.setSectionResizeMode(vh.ResizeMode.Fixed)
        vh.setDefaultSectionSize(24)
        vh.setVisible(False)

        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(self.SelectionMode.NoSelection)
        self.setWordWrap(False)  # makes for better elided labels

        self.resize(500, 500)
        self._rebuild_table()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._rows_checkable:
            # set item style based on check state
            color = self.palette().color(self.foregroundRole())
            font = item.font()
            if item.checkState() == Qt.CheckState.Checked:
                color.setAlpha(255)
                font.setBold(True)
            else:
                color.setAlpha(130)
                font.setBold(False)
            with signals_blocked(self):
                item.setForeground(color)
                item.setFont(font)
        self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._rebuild_table)
        # self._mmc.events.configGroupDeleted.disconnect(self._rebuild_table)
        # self._mmc.events.configDeleted.disconnect(self._rebuild_table)
        # self._mmc.events.configDefined.disconnect(self._rebuild_table)

    def checkGroup(self, group: str) -> None:
        presets = self._mmc.getAvailableConfigs(group)
        if not presets:
            return
        included = [tuple(c)[:2] for c in self._mmc.getConfigData(group, presets[0])]
        for row in range(self.rowCount()):
            prop = cast("DeviceProperty", self.item(row, 0).data(self.PROP_ROLE))
            if (prop.device, prop.name) in included:
                self.item(row, 0).setCheckState(Qt.CheckState.Checked)
            else:
                self.item(row, 0).setCheckState(Qt.CheckState.Unchecked)

    def setRowNumbersVisible(self, visible: bool = True) -> None:
        """Set whether line numbers are visible."""
        self.verticalHeader().setVisible(visible)

    def setRowsCheckable(self, checkable: bool = True) -> None:
        """Set whether individual row checkboxes are visible."""
        self._rows_checkable = checkable
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            flags = item.flags()
            if checkable:
                item.setCheckState(Qt.CheckState.Unchecked)
                flags |= Qt.ItemFlag.ItemIsUserCheckable
            else:
                flags &= ~Qt.ItemFlag.ItemIsUserCheckable
            self.item(row, 0).setFlags(flags)

    def _rebuild_table(self) -> None:
        self.blockSignals(True)
        try:
            self._rebuild_table_inner()
        finally:
            self.blockSignals(False)

    def _rebuild_table_inner(self) -> None:
        self.clearContents()
        props = list(self._mmc.iterProperties(as_object=True))
        self.setRowCount(len(props))

        for i, prop in enumerate(props):
            extra = " 🅿" if prop.isPreInit() else ""
            item = QTableWidgetItem(f"{prop.device}-{prop.name}{extra}")
            item.setData(self.PROP_ROLE, prop)
            if icon_string := DEVICE_TYPE_ICON.get(prop.deviceType()):
                item.setIcon(QIconifyIcon(icon_string, color="Gray"))
            self.setItem(i, 0, item)

            try:
                wdg = PropertyWidget(
                    prop.device,
                    prop.name,
                    mmcore=self._mmc,
                    connect_core=self._connect_core,
                )
                # TODO: this is an over-emission.  if this is a checkable table,
                # and the property is not checked, we should not emit.
                wdg.valueChanged.connect(self.valueChanged)
            except Exception as e:
                logger.error(
                    f"Error creating widget for {prop.device}-{prop.name}: {e}"
                )
                continue

            self.setCellWidget(i, 1, wdg)
            if not self._prop_widgets_enabled:
                wdg.setEnabled(False)

            if prop.isReadOnly():
                # TODO: make this more theme aware
                item.setBackground(QColor("#AAA"))
                wdg.setStyleSheet("QLabel { background-color : #AAA }")

        self.resizeColumnsToContents()
        self.setRowsCheckable(self._rows_checkable)
        # TODO: install eventFilter to prevent mouse wheel from scrolling sliders

    def setReadOnlyDevicesVisible(self, visible: bool = True) -> None:
        """Set whether read-only devices are visible."""
        for row in range(self.rowCount()):
            prop = cast("DeviceProperty", self.item(row, 0).data(self.PROP_ROLE))
            if prop.isReadOnly():
                self.setRowHidden(row, not visible)

    def filterDevices(
        self,
        query: str | Pattern = "",
        *,
        exclude_devices: Iterable[DeviceType] = (),
        include_devices: Iterable[DeviceType] = (),
        include_read_only: bool = True,
        include_pre_init: bool = True,
        always_show_checked: bool = False,
        predicate: Callable[[DeviceProperty], bool | None] | None = None,
    ) -> None:
        """Update the table to only show devices that match the given query/filter.

        Filters are applied in the following order:
        1. If `include_devices` is provided, only devices of the specified types
           will be considered.
        2. If `exclude_devices` is provided, devices of the specified types will be
           hidden (even if they are in `include_devices`).
        3. If `always_show_checked` is True, remaining rows that are checked will
           always be shown, regardless of other filters.
        4. If `predicate` is provided and it returns False, the row is hidden.
        5. If `include_read_only` is False, read-only properties are hidden.
        6. If `include_pre_init` is False, pre-initialized properties are hidden.
        7. Query filtering is applied last, hiding rows that do not match the query.

        Parameters
        ----------
        query : str | Pattern, optional
            A string or regex pattern to match against the device-property names.
            If empty, no filtering is applied, by default ""
        exclude_devices : Iterable[DeviceType], optional
            A list of device types to exclude from the table, by default ()
        include_devices : Iterable[DeviceType], optional
            A list of device types to include in the table, by default ()
        include_read_only : bool, optional
            Whether to include read-only properties in the table, by default True
        include_pre_init : bool, optional
            Whether to include pre-initialized properties in the table, by default True
        always_show_checked : bool, optional
            Whether to always include rows that are checked, by default False.
        predicate : Callable[[DeviceProperty, QTableWidgetItem], bool | None] | None
            A function that takes a `DeviceProperty` and `QTableWidgetItem` and returns
            True to include the row, False to exclude it, or None to skip filtering.
            If None, no additional filtering is applied, by default None
        """
        exclude_devices = set(exclude_devices)
        include_devices = set(include_devices)
        for row in range(self.rowCount()):
            if (item := self.item(row, 0)) is None:
                continue

            if always_show_checked and item.checkState() == Qt.CheckState.Checked:
                self.showRow(row)
                continue

            prop = cast("DeviceProperty", item.data(self.PROP_ROLE))
            dev_type = prop.deviceType()
            if (include_devices and dev_type not in include_devices) or (
                exclude_devices and dev_type in exclude_devices
            ):
                self.hideRow(row)
                continue

            if (
                (predicate and predicate(prop) is False)
                or (not include_read_only and prop.isReadOnly())
                or (not include_pre_init and prop.isPreInit())
            ):
                self.hideRow(row)
                continue

            if query:
                if isinstance(query, str) and query.lower() not in item.text().lower():
                    self.hideRow(row)
                    continue
                elif isinstance(query, Pattern) and not query.search(item.text()):
                    self.hideRow(row)
                    continue

            self.showRow(row)

    def getCheckedProperties(self, *, visible_only: bool = False) -> list[Setting]:
        """Return a list of checked properties.

        Each item in the list is a tuple of (device, property, value).
        """
        # list of properties to add to the group
        # [(device, property, value_to_set), ...]
        dev_prop_val_list: list[Setting] = []
        for row in range(self.rowCount()):
            if (
                (item := self.item(row, 0))
                and item.checkState() == Qt.CheckState.Checked
                and (not visible_only or not self.isRowHidden(row))
            ):
                dev_prop_val_list.append(Setting(*self.getRowData(row)))
        return dev_prop_val_list

    def value(self) -> list[Setting]:
        return self.getCheckedProperties()

    def setValue(self, value: Iterable[tuple[str, str, str]]) -> None:
        self.setCheckedProperties(value, with_value=True)

    def setCheckedProperties(
        self,
        value: Iterable[tuple[str, str, str]],
        with_value: bool = True,
    ) -> None:
        for row in range(self.rowCount()):
            if self.item(row, 0) is None:
                continue
            self.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
            for device, prop, *val in value:
                if self.item(row, 0).text() == f"{device}-{prop}":
                    self.item(row, 0).setCheckState(Qt.CheckState.Checked)
                    wdg = cast("PropertyWidget", self.cellWidget(row, 1))
                    if val and with_value:
                        wdg.setValue(val[0])

    def getRowData(self, row: int) -> tuple[str, str, str]:
        item = self.item(row, 0)
        prop: DeviceProperty = item.data(self.PROP_ROLE)
        wdg = cast("PropertyWidget", self.cellWidget(row, 1))
        return (prop.device, prop.name, str(wdg.value()))

    def setPropertyWidgetsEnabled(self, enabled: bool) -> None:
        """Set whether each widget is enabled."""
        before, self._prop_widgets_enabled = self._prop_widgets_enabled, enabled
        if before != enabled:
            for row in range(self.rowCount()):
                self.cellWidget(row, 1).setEnabled(enabled)

    def uncheckAll(self) -> None:
        """Uncheck all rows."""
        for row in range(self.rowCount()):
            if self.item(row, 0) is None:
                continue
            self.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
