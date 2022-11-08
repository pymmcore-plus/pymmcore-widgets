from functools import partial
from typing import Dict, Optional, Set, Tuple, cast

from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ._core import iter_dev_props
from ._property_widget import PropertyWidget


class _PropertyTable(QTableWidget):
    def __init__(
        self, mmcore: Optional[CMMCorePlus] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(0, 2, parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._rebuild_table)
        self._mmc.events.configGroupDeleted.connect(self._rebuild_table)
        self._mmc.events.configDeleted.connect(self._rebuild_table)
        self._mmc.events.configDefined.connect(self._rebuild_table)
        self.destroyed.connect(self._disconnect)

        self.setMinimumWidth(500)
        self.setHorizontalHeaderLabels(["Property", "Value"])
        self.setColumnWidth(0, 250)
        self.horizontalHeader().setStretchLastSection(True)
        vh = self.verticalHeader()
        vh.setSectionResizeMode(vh.ResizeMode.Fixed)
        vh.setDefaultSectionSize(24)
        vh.setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(self.SelectionMode.NoSelection)
        self.resize(500, 500)
        self._rebuild_table()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._rebuild_table)
        self._mmc.events.configGroupDeleted.disconnect(self._rebuild_table)
        self._mmc.events.configDeleted.disconnect(self._rebuild_table)
        self._mmc.events.configDefined.disconnect(self._rebuild_table)

    def _rebuild_table(self) -> None:
        self.clearContents()
        props = list(iter_dev_props(self._mmc))
        self.setRowCount(len(props))
        for i, (dev, prop) in enumerate(props):
            item = QTableWidgetItem(f"{dev}-{prop}")
            wdg = PropertyWidget(dev, prop, mmcore=self._mmc)
            self.setItem(i, 0, item)
            self.setCellWidget(i, 1, wdg)
            if wdg.isReadOnly():
                # TODO: make this more theme aware
                item.setBackground(QColor("#AAA"))
                wdg.setStyleSheet("QLabel { background-color : #AAA }")

        # TODO: install eventFilter to prevent mouse wheel from scrolling sliders


DevTypeLabels: Dict[str, Tuple[DeviceType, ...]] = {
    "cameras": (DeviceType.CameraDevice,),
    "shutters": (DeviceType.ShutterDevice,),
    "stages": (DeviceType.StageDevice,),
    "wheels, turrets, etc.": (DeviceType.StateDevice,),
}
_d: Set[DeviceType] = set.union(*(set(i) for i in DevTypeLabels.values()))
DevTypeLabels["other devices"] = tuple(set(DeviceType) - _d)


class PropertyBrowser(QDialog):
    """A Widget to browse and change properties of all devices.

    Parameters
    ----------
    parent : Optional[QWidget]
        Optional parent widget. By default, None.
    mmcore: Optional[CMMCorePlus]
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new) [`pymmcore_plus.CMMCorePlus.instance`][].
    """

    def __init__(
        self, parent: Optional[QWidget] = None, *, mmcore: Optional[CMMCorePlus] = None
    ):
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self._prop_table = _PropertyTable(mmcore)
        self._show_read_only: bool = True

        self._filters: Set[DeviceType] = set()
        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        right = QWidget()
        right.setLayout(QVBoxLayout())
        right.layout().addWidget(self._filter_text)
        right.layout().addWidget(self._prop_table)

        left = QWidget()
        left.setLayout(QVBoxLayout())
        left.layout().addWidget(self._make_checkboxes())

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(6, 12, 12, 12)
        self.layout().setSpacing(0)
        self.layout().addWidget(left)
        self.layout().addWidget(right)
        self._mmc.events.systemConfigurationLoaded.connect(self._update_filter)

        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_filter)

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        for r in range(self._prop_table.rowCount()):
            wdg = cast(PropertyWidget, self._prop_table.cellWidget(r, 1))
            if wdg.isReadOnly() and not self._show_read_only:  # sourcery skip
                self._prop_table.hideRow(r)
            elif wdg.deviceType() in self._filters:
                self._prop_table.hideRow(r)
            elif filt and filt not in self._prop_table.item(r, 0).text().lower():
                self._prop_table.hideRow(r)
            else:
                self._prop_table.showRow(r)

    def _toggle_filter(self, label: str) -> None:
        self._filters.symmetric_difference_update(DevTypeLabels[label])
        self._update_filter()

    def _make_checkboxes(self) -> QWidget:
        dev_gb = QGroupBox("Device Type")
        dev_gb.setLayout(QGridLayout())
        dev_gb.layout().setSpacing(6)
        all_btn = QPushButton("All")
        dev_gb.layout().addWidget(all_btn, 0, 0, 1, 1)
        none_btn = QPushButton("None")
        dev_gb.layout().addWidget(none_btn, 0, 1, 1, 1)
        for i, (label, devtypes) in enumerate(DevTypeLabels.items()):
            cb = QCheckBox(label)
            cb.setChecked(devtypes[0] not in self._filters)
            cb.toggled.connect(partial(self._toggle_filter, label))
            dev_gb.layout().addWidget(cb, i + 1, 0, 1, 2)

        @all_btn.clicked.connect  # type: ignore
        def _check_all() -> None:
            for cxbx in dev_gb.findChildren(QCheckBox):
                cxbx.setChecked(True)

        @none_btn.clicked.connect  # type: ignore
        def _check_none() -> None:
            for cxbx in dev_gb.findChildren(QCheckBox):
                cxbx.setChecked(False)

        for i in dev_gb.findChildren(QWidget):
            i.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # type: ignore

        ro = QCheckBox("Show read-only")
        ro.setChecked(self._show_read_only)
        ro.toggled.connect(self._set_show_read_only)
        ro.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        c = QWidget()
        c.setLayout(QVBoxLayout())
        c.layout().addWidget(dev_gb)
        c.layout().addWidget(ro)
        c.layout().addStretch()
        return c

    def _set_show_read_only(self, state: bool) -> None:
        self._show_read_only = state
        self._update_filter()


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    CMMCorePlus.instance().loadSystemConfiguration()
    app = QApplication([])
    table = PropertyBrowser()
    table.show()

    app.exec_()
