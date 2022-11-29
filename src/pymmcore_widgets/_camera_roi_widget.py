from __future__ import annotations

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

# from ._util import block_core

fixed_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
FULL = "Full Chip"
CUSTOM_ROI = "Custom ROI"


class CameraRoiWidget(QWidget):
    """A Widget to control the camera device ROI.

    When the ROI changes, the `roiChanged` Signal is emitted with the current ROI
    (x, y, width, height, comboBoxText)

    [`pymmcore_plus.CMMCoreSignaler`]

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    # (x, y, width, height, comboBoxText)
    roiChanged = Signal(int, int, int, int, str)

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        main_wdg = self._create_main_wdg()
        layout.addWidget(main_wdg)

        self.chip_size_x = 0
        self.chip_size_y = 0

        self._on_sys_cfg_loaded()

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeChanged.connect(self._update_lbl_info)
        self._mmc.events.roiSet.connect(self._on_roi_set)

        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeChanged.disconnect(self._update_lbl_info)
        self._mmc.events.roiSet.disconnect(self._on_roi_set)

    def _create_main_wdg(self) -> QWidget:

        wdg = QWidget()
        layout = QGridLayout()
        layout.setVerticalSpacing(3)
        layout.setHorizontalSpacing(5)
        layout.setContentsMargins(3, 3, 3, 3)
        wdg.setLayout(layout)

        crop_mode = self._create_selection_wdg()
        layout.addWidget(crop_mode, 0, 0)

        self.custorm_roi_group = self._create_custom_roi_group()
        layout.addWidget(self.custorm_roi_group, 0, 1)

        bottom_wdg = QGroupBox()
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        bottom_layout.setContentsMargins(10, 3, 10, 3)
        bottom_wdg.setLayout(bottom_layout)

        self.lbl_info = QLabel()
        bottom_layout.addWidget(self.lbl_info)

        spacer = QSpacerItem(
            10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        bottom_layout.addItem(spacer)

        self.snap_checkbox = QCheckBox(text="autoSnap")
        self.snap_checkbox.setChecked(True)
        bottom_layout.addWidget(self.snap_checkbox)

        self.crop_btn = QPushButton("Crop")
        self.crop_btn.setMinimumWidth(100)
        self.crop_btn.setIcon(icon(MDI6.crop, color=(0, 255, 0)))
        self.crop_btn.setIconSize(QSize(30, 30))
        self.crop_btn.clicked.connect(self._on_crop_pushed)
        bottom_layout.addWidget(self.crop_btn)

        layout.addWidget(bottom_wdg, 1, 0, 1, 2)

        return wdg

    def _create_selection_combo_wdg(self) -> QWidget:

        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        self.cam_roi_combo = QComboBox()
        self.cam_roi_combo.setMinimumWidth(120)
        self.cam_roi_combo.currentTextChanged.connect(self._on_roi_combobox_change)

        layout.addWidget(self.cam_roi_combo)

        return wdg

    def _create_selection_wdg(self) -> QGroupBox:

        wdg = QGroupBox()
        wdg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(3, 3, 3, 3)
        wdg.setLayout(layout)

        combo = self._create_selection_combo_wdg()
        layout.addWidget(combo)

        self.center_checkbox = QCheckBox(text="center custom ROI")
        self.center_checkbox.toggled.connect(self._on_center_checkbox)
        layout.addWidget(self.center_checkbox)

        return wdg

    def _create_custom_roi_group(self) -> QGroupBox:

        group = QGroupBox()
        layout = QGridLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(3, 3, 3, 3)
        group.setLayout(layout)

        roi_start_x_label = QLabel("Start x:")
        roi_start_x_label.setSizePolicy(fixed_sizepolicy)
        self.start_x = QSpinBox()
        self.start_x.setMinimum(0)
        self.start_x.setMaximum(10000)
        self.start_x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_x.valueChanged.connect(self._on_start_spinbox_changed)
        roi_start_y_label = QLabel("Start y:")
        roi_start_y_label.setSizePolicy(fixed_sizepolicy)
        self.start_y = QSpinBox()
        self.start_y.setMinimum(0)
        self.start_y.setMaximum(10000)
        self.start_y.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_y.valueChanged.connect(self._on_start_spinbox_changed)

        layout.addWidget(roi_start_x_label, 1, 0, 1, 1)
        layout.addWidget(self.start_x, 1, 1, 1, 1)
        layout.addWidget(roi_start_y_label, 2, 0, 1, 1)
        layout.addWidget(self.start_y, 2, 1, 1, 1)

        roi_size_label = QLabel("Width:")
        roi_size_label.setSizePolicy(fixed_sizepolicy)
        self.roi_width = QSpinBox()
        self.roi_width.setObjectName("roi_width")
        self.roi_width.setMinimum(1)
        self.roi_width.setMaximum(10000)
        self.roi_width.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.roi_width.valueChanged.connect(self._on_roi_spinbox_changed)
        roi_height_label = QLabel("Height:")
        roi_height_label.setSizePolicy(fixed_sizepolicy)
        self.roi_height = QSpinBox()
        self.roi_height.setObjectName("roi_height")
        self.roi_height.setMinimum(1)
        self.roi_height.setMaximum(10000)
        self.roi_height.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.roi_height.valueChanged.connect(self._on_roi_spinbox_changed)

        layout.addWidget(roi_size_label, 1, 2, 1, 1)
        layout.addWidget(self.roi_width, 1, 3, 1, 1)
        layout.addWidget(roi_height_label, 2, 2, 1, 1)
        layout.addWidget(self.roi_height, 2, 3, 1, 1)

        return group

    def _setEnabled(self, enabled: bool) -> None:
        self.cam_roi_combo.setEnabled(enabled)
        self.center_checkbox.setEnabled(enabled)
        self.custorm_roi_group.setEnabled(enabled)
        self.crop_btn.setEnabled(enabled)
        spin_list = [self.start_x, self.start_y, self.roi_width, self.roi_height]
        self._hide_spinbox_button(spin_list, enabled)

    def _on_sys_cfg_loaded(self) -> None:
        if not self._mmc.getCameraDevice():
            self._setEnabled(False)
            return
        self._setEnabled(True)
        self.chip_size_x = self._mmc.getROI(self._mmc.getCameraDevice())[-2]
        self.chip_size_y = self._mmc.getROI(self._mmc.getCameraDevice())[-1]
        self.roi_width.setMaximum(self.chip_size_x)
        self.roi_height.setMaximum(self.chip_size_y)
        self._reset_start_max()
        self._initialize_wdg()

    def _initialize_wdg(self) -> None:
        with signals_blocked(self.cam_roi_combo):
            items = self._cam_roi_combo_items(self.chip_size_x, self.chip_size_y)
            self.cam_roi_combo.clear()
            self.cam_roi_combo.addItems(items)
            self.cam_roi_combo.setCurrentText(FULL)
        spin_list = [self.start_x, self.start_y, self.roi_width, self.roi_height]
        self._hide_spinbox_button(spin_list, True)
        self._set_roi_groupbox_values(0, 0, self.chip_size_x, self.chip_size_y)
        self.custorm_roi_group.setEnabled(False)
        self.center_checkbox.setEnabled(False)
        self.crop_btn.setEnabled(False)
        with signals_blocked(self.center_checkbox):
            self.center_checkbox.setChecked(True)
        self._update_lbl_info()

    def _cam_roi_combo_items(self, chip_size_x: int, chip_size_y: int) -> list:
        items = [FULL, CUSTOM_ROI]
        options = [8, 6, 4, 2]
        for val in options:
            width = round(chip_size_x / val)
            height = round(chip_size_y / val)
            items.append(f"{width} x {height}")
        return items

    def _on_roi_set(
        self, cam_label: str, x: int, y: int, width: int, height: int
    ) -> None:

        self.start_x.setMaximum(self.chip_size_x)
        self.start_y.setMaximum(self.chip_size_y)

        self._set_roi_groupbox_values(x, y, width, height, False)

        if (x, y, width, height) == (0, 0, self.chip_size_x, self.chip_size_y):
            with signals_blocked(self.cam_roi_combo):
                self.cam_roi_combo.setCurrentText(FULL)
            with signals_blocked(self.center_checkbox):
                self.center_checkbox.setChecked(True)

        elif "x" in self.cam_roi_combo.currentText():
            self._setEnabled(False)
            self.cam_roi_combo.setEnabled(True)

        else:
            with signals_blocked(self.cam_roi_combo):
                self.cam_roi_combo.setCurrentText(CUSTOM_ROI)
            self._setEnabled(True)
            spin_list = [self.start_x, self.start_y, self.roi_width, self.roi_height]
            self._hide_spinbox_button(spin_list, False)
            self.center_checkbox.setChecked(False)

        self._update_lbl_info()

    def _reset_for_custom_roi(self, checkbox_state: bool) -> None:
        self._setEnabled(True)
        spin_list = [self.start_x, self.start_y, self.roi_width, self.roi_height]
        self._hide_spinbox_button(spin_list, False)
        with signals_blocked(self.center_checkbox):
            self.center_checkbox.setChecked(checkbox_state)

    def _update_lbl_info(self) -> None:

        start_x, start_y, width, height = self._get_roi_groupbox_values()

        px_size = self._mmc.getPixelSizeUm() or 0

        width_um = width * px_size
        height_um = height * px_size

        self.lbl_info.setText(
            f"Size: {width} px * {height} px [{width_um} µm * {height_um} µm]"
        )

        if self._mmc.getROI() == [start_x, start_y, width, height]:
            self.lbl_info.setStyleSheet("")
        else:
            self.lbl_info.setStyleSheet("color: magenta;")

    def _on_roi_combobox_change(self, value: str) -> None:
        self.custorm_roi_group.setEnabled(value == CUSTOM_ROI)
        self.center_checkbox.setEnabled(value == CUSTOM_ROI)
        self.crop_btn.setEnabled(value == CUSTOM_ROI)

        with signals_blocked(self.center_checkbox):
            self.center_checkbox.setChecked(value != CUSTOM_ROI)

        spin_list = [self.start_x, self.start_y, self.roi_width, self.roi_height]

        if value == FULL:
            self._hide_spinbox_button(spin_list, True)
            self._mmc.clearROI()

            # TODO: add roiSet signal to mmc.clearROI()
            self._mmc.events.roiSet.emit(
                self._mmc.getCameraDevice(), 0, 0, self.chip_size_x, self.chip_size_y
            )

            if self.snap_checkbox.isChecked():
                self._mmc.snap()

            self.roiChanged.emit(0, 0, self.chip_size_x, self.chip_size_y, FULL)

        elif value == CUSTOM_ROI:
            self._mmc.clearROI()

            # TODO: add roiSet signal to mmc.clearROI()
            # Then here add::
            # with block_core(self._mmc.events):
            #     self._mmc.clearROI()

            if self.snap_checkbox.isChecked():
                self._mmc.snap()

            self._hide_spinbox_button(spin_list, False)
            self._on_center_checkbox(self.center_checkbox.isChecked())

            self._set_start_max_value()

            start_x, start_y, width, height = self._get_roi_groupbox_values()
            self.roiChanged.emit(
                start_x, start_y, width, height, self.cam_roi_combo.currentText()
            )

        else:
            self._hide_spinbox_button(spin_list, True)

            self._check_size_reset_snap()

            width = int(value.split(" x ")[0])
            height = int(value.split(" x ")[1])
            start_x = (self.chip_size_x - width) // 2
            start_y = (self.chip_size_y - height) // 2

            self._set_roi_groupbox_values(start_x, start_y, width, height, False)

            self._mmc.setROI(start_x, start_y, width, height)

            if self.snap_checkbox.isChecked():
                self._mmc.snap()

        self._update_lbl_info()

    def _on_roi_spinbox_changed(self) -> None:

        self._update_lbl_info()

        if self.cam_roi_combo.currentText() != CUSTOM_ROI:
            return

        self._check_size_reset_snap()

        if self.center_checkbox.isChecked():
            self._on_center_checkbox(True)

        self._set_start_max_value()

        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self.roiChanged.emit(start_x, start_y, width, height, CUSTOM_ROI)

    def _on_start_spinbox_changed(self) -> None:
        if not self.start_x.isEnabled() and not self.start_y.isEnabled():
            return

        self._check_size_reset_snap()

        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self.roiChanged.emit(
            start_x, start_y, width, height, self.cam_roi_combo.currentText()
        )

    def _set_start_max_value(self) -> None:
        _, _, wanted_width, wanted_height = self._get_roi_groupbox_values()
        self.start_x.setMaximum(self.chip_size_x - wanted_width)
        self.start_y.setMaximum(self.chip_size_y - wanted_height)

    def _reset_start_max(self) -> None:
        self.start_x.setMaximum(10000)
        self.start_y.setMaximum(10000)

    def _set_roi_groupbox_values(
        self, x: int, y: int, width: int, height: int, signal: bool = True
    ) -> None:
        self._reset_start_max()
        self.start_x.setValue(x)
        self.start_y.setValue(y)
        if signal:
            self.roi_width.setValue(width)
            self.roi_height.setValue(height)
        else:
            with signals_blocked(self.roi_width):
                self.roi_width.setValue(width)
            with signals_blocked(self.roi_height):
                self.roi_height.setValue(height)

    def _get_roi_groupbox_values(self) -> tuple:
        start_x = self.start_x.value()
        start_y = self.start_y.value()
        width = self.roi_width.value()
        height = self.roi_height.value()
        return start_x, start_y, width, height

    def _on_center_checkbox(self, state: bool) -> None:

        self.start_x.setEnabled(not state)
        self.start_y.setEnabled(not state)
        self._hide_spinbox_button([self.start_x, self.start_y], state)

        if not state or self.cam_roi_combo.currentText() != CUSTOM_ROI:
            return

        self._check_size_reset_snap()

        _, _, wanted_width, wanted_height = self._get_roi_groupbox_values()
        start_x = (self.chip_size_x - wanted_width) // 2
        start_y = (self.chip_size_y - wanted_height) // 2

        self.start_x.setValue(start_x)
        self.start_y.setValue(start_y)

        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self.roiChanged.emit(start_x, start_y, width, height, CUSTOM_ROI)

        self._update_lbl_info()

    def _hide_spinbox_button(self, spin_list: list[QSpinBox], hide: bool) -> None:
        for spin in spin_list:
            if hide:
                spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            else:
                spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)

    def _check_size_reset_snap(self, snap: bool = True) -> None:
        x, y, w, h = self._mmc.getROI()
        roi_width = x + w
        roi_height = y + h
        if roi_width < self.chip_size_x or roi_height < self.chip_size_y:
            self._mmc.clearROI()
            if self.snap_checkbox.isChecked():
                self._mmc.snap()

    def _on_crop_pushed(self) -> None:
        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self._mmc.setROI(start_x, start_y, width, height)
        self._update_lbl_info()
        if self.snap_checkbox.isChecked():
            self._mmc.snap()
