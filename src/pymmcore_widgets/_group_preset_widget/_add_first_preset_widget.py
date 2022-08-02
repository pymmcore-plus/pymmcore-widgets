from typing import Optional

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._property_widget import PropertyWidget


class AddFirstPresetWidget(QDialog):
    """A widget to create the first specified group's preset."""

    def __init__(
        self,
        group: str,
        preset: str,
        dev_prop_val_list: list,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = CMMCorePlus.instance()
        self._group = group
        self._preset = preset
        self._dev_prop_val_list = dev_prop_val_list

        self._create_gui()

        self._populate_table()

    def _create_gui(self) -> None:

        self.setWindowTitle(f"Add the first Preset to the new '{self._group}' Group")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        top_wdg = self._create_top_wdg()
        wdg_layout.addWidget(top_wdg)

        self.table = _Table()
        wdg_layout.addWidget(self.table)

        bottom_wdg = self._create_bottom_wdg()
        wdg_layout.addWidget(bottom_wdg)

        main_layout.addWidget(wdg)

    def _create_top_wdg(self) -> QGroupBox:
        wdg = QGroupBox()
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(5)
        wdg_layout.setContentsMargins(5, 5, 5, 5)
        wdg.setLayout(wdg_layout)

        lbl_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        gp_lbl = QLabel(text="Group:")
        gp_lbl.setSizePolicy(lbl_sizepolicy)
        group_name_lbl = QLabel(text=f"{self._group}")
        group_name_lbl.setSizePolicy(lbl_sizepolicy)

        ps_lbl = QLabel(text="Preset:")
        ps_lbl.setSizePolicy(lbl_sizepolicy)
        self.preset_name_lineedit = QLineEdit()
        self.preset_name_lineedit.setText(f"{self._preset}")

        spacer = QSpacerItem(30, 10, QSizePolicy.Fixed, QSizePolicy.Fixed)

        wdg_layout.addWidget(gp_lbl)
        wdg_layout.addWidget(group_name_lbl)
        wdg_layout.addItem(spacer)
        wdg_layout.addWidget(ps_lbl)
        wdg_layout.addWidget(self.preset_name_lineedit)

        return wdg

    def _create_bottom_wdg(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(5)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        self.apply_button = QPushButton(text="Create Preset")
        self.apply_button.setSizePolicy(
            QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        )
        self.apply_button.clicked.connect(self._create_first_preset)

        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Fixed)

        wdg_layout.addItem(spacer)
        wdg_layout.addWidget(self.apply_button)

        return wdg

    def _populate_table(self) -> None:

        self.table.clearContents()

        self.table.setRowCount(len(self._dev_prop_val_list))
        for idx, (dev, prop, _) in enumerate(self._dev_prop_val_list):
            item = QTableWidgetItem(f"{dev}-{prop}")
            wdg = PropertyWidget(dev, prop, core=self._mmc)
            wdg._value_widget.valueChanged.disconnect()  # type: ignore
            self.table.setItem(idx, 0, item)
            self.table.setCellWidget(idx, 1, wdg)

    def _create_first_preset(self) -> None:

        dev_prop_val = []
        for row in range(self.table.rowCount()):
            device_property = self.table.item(row, 0).text()
            dev = device_property.split("-")[0]
            prop = device_property.split("-")[1]
            value = str(self.table.cellWidget(row, 1).value())
            dev_prop_val.append((dev, prop, value))

        self._preset = self.preset_name_lineedit.text()

        self._mmc.defineConfigFromDevicePropertyValueList(  # type: ignore
            self._group, self._preset, dev_prop_val
        )

        self.close()
        self.parent().close()


class _Table(QTableWidget):
    """Set table properties for EditPresetWidget."""

    def __init__(self) -> None:
        super().__init__()
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        hdr.setDefaultAlignment(Qt.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(vh.Fixed)
        vh.setDefaultSectionSize(24)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Device-Property", "Value"])
