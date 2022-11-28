from typing import Iterable, Optional, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceProperty, DeviceType
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QAbstractScrollArea, QTableWidget, QTableWidgetItem, QWidget
from superqt.fonticon import icon

from pymmcore_widgets._property_widget import PropertyWidget

ICONS: dict[DeviceType, str] = {
    DeviceType.Camera: MDI6.camera,
    DeviceType.Shutter: MDI6.camera_iris,
    DeviceType.Stage: MDI6.axis_arrow,
    DeviceType.StateDevice: MDI6.state_machine,
    DeviceType.XYStage: MDI6.tablet,
    DeviceType.AutoFocus: MDI6.auto_upload,
    DeviceType.CoreDevice: MDI6.checkbox_blank_circle_outline,
}


class DevicePropertyTable(QTableWidget):

    PROP_ROLE = QTableWidgetItem.ItemType.UserType + 1

    def __init__(
        self, mmcore: Optional[CMMCorePlus] = None, parent: Optional[QWidget] = None
    ):
        rows = 0
        cols = 2
        super().__init__(rows, cols, parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._rebuild_table)

        self._mmc.events.configGroupDeleted.connect(self._rebuild_table)
        self._mmc.events.configDeleted.connect(self._rebuild_table)
        self._mmc.events.configDefined.connect(self._rebuild_table)
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
        self._mmc.events.configGroupDeleted.disconnect(self._rebuild_table)
        self._mmc.events.configDeleted.disconnect(self._rebuild_table)
        self._mmc.events.configDefined.disconnect(self._rebuild_table)

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
            item.setIcon(icon(ICONS[prop.deviceType()], opacity=0.5, color="blue"))
            self.setItem(i, 0, item)

            wdg = PropertyWidget(prop.device, prop.name, mmcore=self._mmc)
            self.setCellWidget(i, 1, wdg)

            if prop.isReadOnly():
                # TODO: make this more theme aware
                item.setBackground(QColor("#AAA"))
                wdg.setStyleSheet("QLabel { background-color : #AAA }")

        self.resizeColumnsToContents()
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
    ) -> None:
        """Set whether devices of a given type are visible."""
        exclude_devices = set(exclude_devices)
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            prop = cast(DeviceProperty, item.data(self.PROP_ROLE))
            if (
                (prop.isReadOnly() and not include_read_only)
                or (prop.deviceType() in exclude_devices)
                or (query and query not in item.text().lower())
            ):
                self.hideRow(row)
            else:
                self.showRow(row)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    CMMCorePlus.instance().loadSystemConfiguration()
    app = QApplication([])
    table = DevicePropertyTable()
    table.show()

    app.exec_()
