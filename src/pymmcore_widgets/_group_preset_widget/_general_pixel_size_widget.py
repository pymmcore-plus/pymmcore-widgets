from typing import TYPE_CHECKING

from fonticon_mdi6 import MDI6
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)
from superqt.fonticon import icon

from pymmcore_widgets._device_property_table import DevicePropertyTable
from pymmcore_widgets._device_type_filter import DeviceTypeFilters
from pymmcore_widgets.useq_widgets import DataTableWidget
from pymmcore_widgets.useq_widgets._column_info import FloatColumn, TextColumn

if TYPE_CHECKING:
    from PyQt6.QtGui import QAction
else:
    from qtpy.QtGui import QAction

FIXED = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

# mmc = CMMCorePlus.instance()
# mmc.loadSystemConfiguration()

# for c in mmc.getAvailablePixelSizeConfigs():
#     print(c)
#     print(mmc.getPixelSizeConfigData(c))


class PixelTable(DataTableWidget):
    ID = TextColumn(
        key="id", header="pixel configuration name", default=None, is_row_selector=False
    )
    VALUE = FloatColumn(
        key="px", header="pixel value [µm]", default=0, is_row_selector=False
    )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self.act_edit = QAction(icon(MDI6.pencil, color="#666"), "Edit", self)
        self.act_edit.triggered.connect(self._edit_pixel_size)
        self._toolbar.insertAction(self.act_check_all, self.act_edit)

        self._toolbar.removeAction(self.act_check_all)
        self._toolbar.removeAction(self.act_check_none)

    def _edit_pixel_size(self) -> None:
        pass

    def _add_row(self) -> None:
        """Add a new to the end of the table."""
        # self._new = NewPixelConfiguration()
        self._new = PixelConfigurationWizard()
        self._new.show()

        if self._new.exec_():
            super()._add_row()
            # TODO: add tooltip with configuration data


class PixelConfigurationWizard(QWizard):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Pixel Configuration Wizard")

        self._prop_page = PropertyPage()
        self.addPage(self._prop_page)


class PropertyPage(QWizardPage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setTitle("Select properties")
        self.setSubTitle(
            "Select the properties you want to include in the pixel configuration."
        )


class NewPixelConfiguration(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("New Pixel Configuration")

        # property table (right wdg)
        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        # self._filter_text.textChanged.connect(self._update_filter)

        self._prop_table = DevicePropertyTable(enable_property_widgets=False)
        self._prop_table.setRowsCheckable(True)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        # right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._filter_text)
        right_layout.addWidget(self._prop_table)

        # pixel configuration name, pixel size and DeviceTypeFilters (left wdg)
        cfg_wdg = QWidget()
        cfg_layout = QHBoxLayout(cfg_wdg)
        # cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_lbl = QLabel(text="Pixel Configuration Name:")
        cfg_lbl.setSizePolicy(FIXED)
        self._px_cfg_name = QLineEdit()
        cfg_layout.addWidget(cfg_lbl)
        cfg_layout.addWidget(self._px_cfg_name)

        px_wdg = QWidget()
        px_layout = QHBoxLayout(px_wdg)
        # px_layout.setContentsMargins(0, 0, 0, 0)
        px_val_lbl = QLabel(text="Pixel Size [µm]:")
        px_val_lbl.setSizePolicy(FIXED)
        self._px_value = QDoubleSpinBox()
        self._px_value.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        px_layout.addWidget(px_val_lbl)
        px_layout.addWidget(self._px_value)

        self._device_filters = DeviceTypeFilters()
        # self._device_filters.filtersChanged.connect(self._update_filter)
        self._device_filters.setShowReadOnly(False)
        self._device_filters._read_only_checkbox.hide()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        # left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        left_layout.addWidget(cfg_wdg)
        left_layout.addWidget(px_wdg)
        left_layout.addWidget(self._device_filters)

        # central widget
        central_wdg = QWidget()
        central_layout = QHBoxLayout(central_wdg)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(left)
        central_layout.addWidget(right)

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(central_wdg)

        # QDialog buttons
        btns = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox = QDialogButtonBox(btns)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        main_layout.addWidget(buttonBox)


from pymmcore_plus import CMMCorePlus  # noqa: E402

app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
px = PixelTable()
px.show()
app.exec_()
