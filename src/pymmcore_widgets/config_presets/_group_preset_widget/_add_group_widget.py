from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.device_properties._device_property_table import (
    DevicePropertyTable,
)
from pymmcore_widgets.device_properties._device_type_filter import DeviceTypeFilters

from ._add_first_preset_widget import AddFirstPresetWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent


class AddGroupWidget(QDialog):
    """Widget to create a new group."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self._mmc = CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._update_filter)

        self._create_gui()

        self.destroyed.connect(self._disconnect)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Close also 'AddFirstPresetWidget' if is open."""
        if hasattr(self, "_first_preset_wdg"):
            self._first_preset_wdg.close()  # type: ignore
        event.accept()

    def _create_gui(self) -> None:
        self.setWindowTitle("Create a new Group")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        group_lineedit = self._create_group_lineedit_wdg()
        main_layout.addWidget(group_lineedit)

        table = self._create_table_wdg()
        main_layout.addWidget(table)

        btn = self._create_button_wdg()
        main_layout.addWidget(btn)

    def _create_group_lineedit_wdg(self) -> QGroupBox:
        wdg = QGroupBox()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        wdg.setLayout(layout)

        group_lbl = QLabel(text="Group name:")
        group_lbl.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )

        self.group_lineedit = QLineEdit()

        layout.addWidget(group_lbl)
        layout.addWidget(self.group_lineedit)

        return wdg

    def _create_table_wdg(self) -> QGroupBox:
        wdg = QGroupBox()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        wdg.setLayout(layout)

        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        self._prop_table = DevicePropertyTable(enable_property_widgets=False)
        self._prop_table.setRowsCheckable(True)
        self._device_filters = DeviceTypeFilters()
        self._device_filters.filtersChanged.connect(self._update_filter)
        self._device_filters.setShowReadOnly(False)
        self._device_filters._read_only_checkbox.hide()

        right = QWidget()
        right.setLayout(QVBoxLayout())
        right.layout().addWidget(self._filter_text)
        right.layout().addWidget(self._prop_table)

        left = QWidget()
        left.setLayout(QVBoxLayout())
        left.layout().addWidget(self._device_filters)

        self.layout().addWidget(left)
        self.layout().addWidget(right)
        layout.addWidget(left)
        layout.addWidget(right)

        return wdg

    def _create_button_wdg(self) -> QWidget:
        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        wdg.setLayout(layout)

        self.info_lbl = QLabel()

        self.new_group_btn = QPushButton(text="Create New Group")
        self.new_group_btn.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        self.new_group_btn.clicked.connect(self._add_group)

        layout.addWidget(self.info_lbl)
        layout.addWidget(self.new_group_btn)

        return wdg

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_filter)

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt,
            exclude_devices=self._device_filters.filters(),
            include_read_only=self._device_filters.showReadOnly(),
            include_pre_init=self._device_filters.showPreInitProps(),
        )

    def _add_group(self) -> None:
        group = self.group_lineedit.text()

        if not group:
            warnings.warn("Give a name to the group!", stacklevel=2)
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText("Give a name to the group!")
            return

        if group in self._mmc.getAvailableConfigGroups():
            warnings.warn(f"There is already a preset called '{group}'.", stacklevel=2)
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText(f"'{group}' already exist!")
            return

        # [(device, property, value_to_set), ...]
        dev_prop_val_list = self._prop_table.getCheckedProperties()

        if not dev_prop_val_list:
            warnings.warn("Select at lest one property!", stacklevel=2)
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText("Select at lest one property!")
            return

        if hasattr(self, "_first_preset_wdg"):
            self._first_preset_wdg.close()  # type: ignore
        self._first_preset_wdg = AddFirstPresetWidget(
            group, dev_prop_val_list, parent=self
        )
        self._first_preset_wdg.show()

        self.info_lbl.setStyleSheet("")
        self.info_lbl.setText("")
