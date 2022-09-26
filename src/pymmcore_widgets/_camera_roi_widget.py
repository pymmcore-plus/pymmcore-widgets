from typing import List, Tuple

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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

fixed_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class CameraRoiWidget(QWidget):
    """
    A Widget to control the camera device ROI.

    When the ROI changes, the roiInfo Signal is emitted.
    """

    roiInfo = Signal(int, int, int, int, str)

    def __init__(self) -> None:
        super().__init__()

        self._mmc = CMMCorePlus.instance()

        self._create_gui()

        self.chip_size_x = 0
        self.chip_size_y = 0

        self._on_sys_cfg_loaded()

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        # self._mmc.events.propertyChanged.connect(self._on_property_changed)
        self._mmc.events.pixelSizeChanged.connect(self._update_lbl_info)
        # new signal in pymmcore-plus
        self._mmc.events.roiSet.connect(self._on_roi_set)

    def _create_gui(self) -> None:  # sourcery skip: class-extract-method

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        main_wdg = self._create_main_wdg()
        layout.addWidget(main_wdg)

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

    def _create_selection_wdg(self) -> QWidget:

        wdg = QGroupBox()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
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
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(layout)

        roi_start_x_label = QLabel("Start x:")
        roi_start_x_label.setSizePolicy(fixed_sizepolicy)
        self.start_x = QSpinBox()
        self.start_x.setMinimum(0)
        self.start_x.setMaximum(10000)
        self.start_x.setAlignment(Qt.AlignCenter)
        self.start_x.valueChanged.connect(self._on_start_spinbox_changed)
        roi_start_y_label = QLabel("Start y:")
        roi_start_y_label.setSizePolicy(fixed_sizepolicy)
        self.start_y = QSpinBox()
        self.start_y.setMinimum(0)
        self.start_y.setMaximum(10000)
        self.start_y.setAlignment(Qt.AlignCenter)
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
        self.roi_width.setAlignment(Qt.AlignCenter)
        self.roi_width.valueChanged.connect(self._on_roi_spinbox_changed)
        roi_height_label = QLabel("Height:")
        roi_height_label.setSizePolicy(fixed_sizepolicy)
        self.roi_height = QSpinBox()
        self.roi_height.setObjectName("roi_height")
        self.roi_height.setMinimum(1)
        self.roi_height.setMaximum(10000)
        self.roi_height.setAlignment(Qt.AlignCenter)
        self.roi_height.valueChanged.connect(self._on_roi_spinbox_changed)

        layout.addWidget(roi_size_label, 1, 2, 1, 1)
        layout.addWidget(self.roi_width, 1, 3, 1, 1)
        layout.addWidget(roi_height_label, 2, 2, 1, 1)
        layout.addWidget(self.roi_height, 2, 3, 1, 1)

        return group

    def _create_main_wdg(self) -> QWidget:

        wdg = QWidget()
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(layout)

        crop_mode = self._create_selection_wdg()
        layout.addWidget(crop_mode, 0, 0)

        self.custorm_roi_group = self._create_custom_roi_group()
        layout.addWidget(self.custorm_roi_group, 0, 1)

        self.crop_btn = QPushButton("Crop")
        self.crop_btn.setIcon(icon(MDI6.crop, color=(0, 255, 0)))
        self.crop_btn.setIconSize(QSize(30, 30))
        self.crop_btn.clicked.connect(self._on_crop_pushed)
        layout.addWidget(self.crop_btn, 1, 0)

        self.lbl_info = QLabel()
        self.lbl_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_info, 1, 1)

        return wdg

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
        with signals_blocked(self.cam_roi_combo):
            items = self._cam_roi_combo_items(self.chip_size_x, self.chip_size_y)
            self.cam_roi_combo.clear()
            self.cam_roi_combo.addItems(items)
            self.cam_roi_combo.setCurrentText("Full")
        self._on_roi_combobox_change("Full", snap=False)

    def _cam_roi_combo_items(self, chip_size_x: int, chip_size_y: int) -> list:
        items = ["Full", "ROI"]
        options = [8, 6, 4, 2]
        for val in options:
            width = round(chip_size_x / val)
            height = round(chip_size_y / val)
            items.append(f"{width} x {height}")
        return items

    # def _on_property_changed(self, device: str, property: str, value: str) -> None:
    #     # TODO: test if the camera prop for the roi size is
    #     # always called "OnCameraCCDXSize", "OnCameraCCDYSize" like in the demo cfg
    #     if device != self._mmc.getCameraDevice():
    #         return
    #     if property in {"OnCameraCCDXSize", "OnCameraCCDYSize"}:
    #         wdg = self.roi_width if "X" in property else self.roi_height
    #         if value == wdg.value():
    #             return
    #         wdg.setValue(int(value))
    #         with signals_blocked(self.center_checkbox):
    #             self.center_checkbox.setChecked(True)
    #         with signals_blocked(self.cam_roi_combo):
    #             self.cam_roi_combo.setCurrentText("ROI")
    #         self._on_roi_combobox_change("ROI")

    def _on_roi_set(
        self, cam_label: str, x: int, y: int, width: int, height: int
    ) -> None:

        with signals_blocked(self.center_checkbox):
            self.center_checkbox.setChecked(False)
        with signals_blocked(self.cam_roi_combo):
            self.cam_roi_combo.setCurrentText("ROI")
        self.start_x.setMaximum(self.chip_size_x)
        self.start_y.setMaximum(self.chip_size_y)

        self._set_roi_groupbox_values(x, y, width, height, False)
        self._on_roi_combobox_change("ROI")

    def _update_lbl_info(self) -> None:

        _, _, width, height = self._get_roi_groupbox_values()

        px_size = self._mmc.getPixelSizeUm() or 0

        width_um = width * px_size
        height_um = height * px_size

        self.lbl_info.setText(
            f"Size: {width} px * {height} px [{width_um} µm * {height_um} µm]"
        )

    def _on_roi_combobox_change(self, value: str, snap: bool = True) -> None:
        self.custorm_roi_group.setEnabled(value == "ROI")
        self.center_checkbox.setEnabled(value == "ROI")
        self.crop_btn.setEnabled(value != "Full")

        with signals_blocked(self.center_checkbox):
            self.center_checkbox.setChecked(value != "ROI")

        if snap and self._mmc.getCameraDevice():
            self._mmc.snap()

        spin_list = [self.start_x, self.start_y, self.roi_width, self.roi_height]

        if value == "Full":
            self._hide_spinbox_button(spin_list, True)
            self._mmc.clearROI()
            # self._reset_OnCameraCCD_property()
            self._set_roi_groupbox_values(0, 0, self.chip_size_x, self.chip_size_y)

            self.roiInfo.emit(0, 0, self.chip_size_x, self.chip_size_y, "Full")

        elif value == "ROI":
            self._hide_spinbox_button(spin_list, False)
            self._on_center_checkbox(self.center_checkbox.isChecked())

            self._set_start_max_value()

            start_x, start_y, width, height = self._get_roi_groupbox_values()
            self.roiInfo.emit(
                start_x, start_y, width, height, self.cam_roi_combo.currentText()
            )

        else:
            self._hide_spinbox_button(spin_list, True)

            self._reset_and_snap()

            width = int(value.split(" x ")[0])
            height = int(value.split(" x ")[1])
            start_x = (self.chip_size_x - width) // 2
            start_y = (self.chip_size_y - height) // 2

            self._set_roi_groupbox_values(start_x, start_y, width, height, False)
            self.roiInfo.emit(
                start_x, start_y, width, height, self.cam_roi_combo.currentText()
            )

        self._update_lbl_info()

    # def _reset_OnCameraCCD_property(self) -> None:
    #     if self._mmc.getProperty(
    #         self._mmc.getCameraDevice(), "OnCameraCCDXSize"
    #     ) != str(self.chip_size_x):
    #         self._mmc.setProperty(
    #             self._mmc.getCameraDevice(), "OnCameraCCDXSize", self.chip_size_x
    #         )
    #     if self._mmc.getProperty(
    #         self._mmc.getCameraDevice(), "OnCameraCCDYSize"
    #     ) != str(self.chip_size_y):
    #         self._mmc.setProperty(
    #             self._mmc.getCameraDevice(), "OnCameraCCDYSize", self.chip_size_y
    #         )

    def _on_roi_spinbox_changed(self) -> None:

        self._update_lbl_info()

        if self.cam_roi_combo.currentText() != "ROI":
            return

        x, y, w, h = self._mmc.getROI()
        roi_width = x + w
        roi_height = y + h
        if roi_width < self.chip_size_x or roi_height < self.chip_size_y:
            self._reset_and_snap()

        self._set_start_max_value()

        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self.roiInfo.emit(start_x, start_y, width, height, "ROI")

    def _on_start_spinbox_changed(self) -> None:
        if not self.start_x.isEnabled() and not self.start_y.isEnabled():
            return

        x, y, w, h = self._mmc.getROI()
        roi_width = x + w
        roi_height = y + h
        if roi_width < self.chip_size_x or roi_height < self.chip_size_y:
            self._reset_and_snap()

        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self.roiInfo.emit(
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

    def _get_roi_groupbox_values(self) -> Tuple:
        start_x = self.start_x.value()
        start_y = self.start_y.value()
        width = self.roi_width.value()
        height = self.roi_height.value()
        return start_x, start_y, width, height

    def _on_center_checkbox(self, state: bool) -> None:

        self.start_x.setEnabled(not state)
        self.start_y.setEnabled(not state)
        self._hide_spinbox_button([self.start_x, self.start_y], state)

        if not state or self.cam_roi_combo.currentText() != "ROI":
            return

        self._reset_and_snap()

        _, _, wanted_width, wanted_height = self._get_roi_groupbox_values()
        start_x = (self.chip_size_x - wanted_width) // 2
        start_y = (self.chip_size_y - wanted_height) // 2

        self.start_x.setValue(start_x)
        self.start_y.setValue(start_y)

        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self.roiInfo.emit(start_x, start_y, width, height, "ROI")

    def _hide_spinbox_button(self, spin_list: List[QSpinBox], hide: bool) -> None:
        for spin in spin_list:
            if hide:
                spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            else:
                spin.setButtonSymbols(QAbstractSpinBox.PlusMinus)

    def _reset_and_snap(self) -> None:
        self._mmc.clearROI()
        self._mmc.snap()

    def _on_crop_pushed(self) -> None:
        start_x, start_y, width, height = self._get_roi_groupbox_values()
        self._mmc.setROI(start_x, start_y, width, height)
        # self._mmc.setProperty(self._mmc.getCameraDevice(), "OnCameraCCDXSize", width)
        # self._mmc.setProperty(self._mmc.getCameraDevice(), "OnCameraCCDYSize", height)
        self._mmc.snap()

        # self.center_checkbox.setEnabled(False)
        # self.custorm_roi_group.setEnabled(False)
        # spin_list = [self.start_x, self.start_y, self.roi_width, self.roi_height]
        # self._hide_spinbox_button(spin_list, True)
