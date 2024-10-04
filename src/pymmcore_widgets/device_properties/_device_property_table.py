from __future__ import annotations

from logging import getLogger
from typing import Iterable, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty, DeviceType
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QAbstractScrollArea, QTableWidget, QTableWidgetItem, QWidget
from superqt.fonticon import icon

from pymmcore_widgets._icons import ICONS

from ._property_widget import PropertyWidget

logger = getLogger(__name__)


class DevicePropertyTable(QTableWidget):
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

        # If we enable these, then the edit group dialog will lose all of it's checks
        # whenever modify group button is clicked.  However, We don't want this widget
        # to have to be aware of a current group (or do we?)
        # self._mmc.events.configGroupDeleted.connect(self._rebuild_table)
        # self._mmc.events.configDeleted.connect(self._rebuild_table)
        # self._mmc.events.configDefined.connect(self._rebuild_table)

        self.destroyed.connect(self._disconnect)

        self.setMinimumWidth(500)
        self.setHorizontalHeaderLabels(["Property", "Value"])
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
            prop = cast(DeviceProperty, self.item(row, 0).data(self.PROP_ROLE))
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
        self.clearContents()
        props = list(self._mmc.iterProperties(as_object=True))
        self.setRowCount(len(props))
        for i, prop in enumerate(props):
            item = QTableWidgetItem(f"{prop.device}-{prop.name}")
            item.setData(self.PROP_ROLE, prop)
            icon_string = ICONS.get(prop.deviceType())
            if icon_string:
                item.setIcon(icon(icon_string, color="Gray"))
            self.setItem(i, 0, item)

            try:
                wdg = PropertyWidget(
                    prop.device,
                    prop.name,
                    mmcore=self._mmc,
                    connect_core=self._connect_core,
                )
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
            prop = cast(DeviceProperty, self.item(row, 0).data(self.PROP_ROLE))
            if prop.isReadOnly():
                self.setRowHidden(row, not visible)

    def filterDevices(
        self,
        query: str = "",
        exclude_devices: Iterable[DeviceType] = (),
        include_read_only: bool = True,
        include_pre_init: bool = True,
        init_props_only: bool = False,
    ) -> None:
        """Update the table to only show devices that match the given query/filter."""
        exclude_devices = set(exclude_devices)
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            prop = cast(DeviceProperty, item.data(self.PROP_ROLE))
            if (
                (prop.isReadOnly() and not include_read_only)
                or (prop.isPreInit() and not include_pre_init)
                or (init_props_only and not prop.isPreInit())
                or (prop.deviceType() in exclude_devices)
                or (query and query.lower() not in item.text().lower())
            ):
                self.hideRow(row)
            else:
                self.showRow(row)

    def getCheckedProperties(self) -> list[tuple[str, str, str]]:
        """Return a list of checked properties.

        Each item in the list is a tuple of (device, property, value).
        """
        # list of properties to add to the group
        # [(device, property, value_to_set), ...]
        dev_prop_val_list: list[tuple[str, str, str]] = []
        for row in range(self.rowCount()):
            if self.item(row, 0) is None:
                continue
            if self.item(row, 0).checkState() == Qt.CheckState.Checked:
                dev_prop_val_list.append(self.getRowData(row))
        return dev_prop_val_list

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
