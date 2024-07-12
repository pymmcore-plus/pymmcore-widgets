from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QFileDialog, QVBoxLayout, QWidget, QWizard
from superqt.utils import signals_blocked
from useq import RandomPoints, RelativePosition, WellPlatePlan

from pymmcore_widgets.hcs._calibration_widget._calibration_widget import (
    _CalibrationData,
)

from ._main_wizard_pages import FOVSelectorPage, PlateCalibrationPage, PlatePage

if TYPE_CHECKING:
    from useq import WellPlate


class HCSWizard(QWizard):
    """A wizard to setup an High Content experiment.

    This widget can be used to select a plate, calibrate it, and then select the FOVs
    to image in different modes (Center, RandomPoint or GridRowsColumns).

    Parameters
    ----------
    parent : QWidget | None
        The parent widget. By default, None.
    mmcore : CMMCorePlus | None
        The CMMCorePlus instance. By default, None.
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setWindowTitle("HCS Wizard")

        # add custom button to save
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        _save_btn = self.button(QWizard.WizardButton.CustomButton1)
        _save_btn.setText("Save")
        _save_btn.clicked.connect(self._save)
        self.setButton(QWizard.WizardButton.CustomButton1, _save_btn)
        # add custom button to load
        self.setOption(QWizard.WizardOption.HaveCustomButton2, True)
        _load_btn = self.button(QWizard.WizardButton.CustomButton2)
        _load_btn.setText("Load")
        _load_btn.clicked.connect(self._load)
        self.setButton(QWizard.WizardButton.CustomButton2, _load_btn)

        # layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 50, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._plate: WellPlate | None = None

        # setup plate page
        self.plate_page = PlatePage(self)
        self.plate_page._plate_widget.valueChanged.connect(self._on_plate_changed)

        # setup calibration page
        self.calibration_page = PlateCalibrationPage(self, self._mmc)

        # setup fov page
        self.fov_page = FOVSelectorPage(self)

        # add pages to wizard
        self.addPage(self.plate_page)
        self.addPage(self.calibration_page)
        self.addPage(self.fov_page)

        # connections
        self._mmc.events.pixelSizeChanged.connect(self._on_px_size_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)

        self.plate_page._plate_widget.valueChanged.connect(self._emit_value_changed)
        self.fov_page._fov_widget.valueChanged.connect(self._emit_value_changed)
        self.calibration_page._calibration.valueChanged.connect(
            self._emit_value_changed
        )

        self._init_widget()

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> WellPlatePlan | None:
        """Return the values of the wizard."""
        if self._plate is None:
            return None

        selected_wells = self.plate_page.value().wells
        # order all x and all y in 2 seoarated lists
        all_columns = [well.column for well in selected_wells]
        all_rows = [well.row for well in selected_wells]

        if not all_columns or not all_rows:
            return None

        calibration = self.calibration_page.value()
        if calibration is None:
            return None

        if not calibration.calibrated:
            return None

        if calibration.a1_center_xy is None:
            return None

        _, mode = self.fov_page.value()

        if mode is None:
            return None

        return WellPlatePlan(
            plate=self._plate,
            a1_center_xy=calibration.a1_center_xy,
            rotation=calibration.rotation,
            well_points_plan=(
                RelativePosition(x=mode.x, y=mode.y)
                if isinstance(mode, Center)
                else mode
            ),
            selected_wells=(all_rows, all_columns),
        )

    def setValue(self, value: WellPlatePlan) -> None:
        """Set the values of the wizard."""
        self._plate = value.plate

        # update the plate page
        names = value.selected_well_names
        cols_rows = value.selected_well_indices
        # convert to Well objects
        paired_wells = [
            Well(name=name, row=position[0], column=position[1])
            for name, position in zip(names, cols_rows)
        ]
        with signals_blocked(self.plate_page._plate_widget):
            self.plate_page.setValue(PlateInfo(value.plate, paired_wells))

        # update calibration page
        calibration = _CalibrationData(
            calibrated=True,
            plate=value.plate,
            a1_center_xy=value.a1_center_xy,
            rotation=value.rotation or 0.0,
        )
        self.calibration_page.setValue(calibration)

        # update fov page
        mode = value.well_points_plan

        if isinstance(mode, RelativePosition):
            fov_width, fov_height = self._get_fov_size()
            mode = Center(
                x=mode.x, y=mode.y, fov_width=fov_width, fov_height=fov_height
            )

        self.fov_page.setValue(value.plate, mode)

        self.valueChanged.emit(value)

    def isCalibrated(self) -> bool:
        """Return True if the calibration is done."""
        return self.calibration_page.isCalibrated()

    def accept(self) -> None:
        """Emit the valueChanged signal when the wizard is accepted."""
        self.valueChanged.emit(self.value())

    # _________________________PRIVATE METHODS_________________________ #

    def _emit_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    def _init_widget(self) -> None:
        """Initialize the wizard widget."""
        self._plate = self.plate_page.value().plate
        self.calibration_page.setValue(_CalibrationData(plate=self._plate))
        fov_w, fov_h = self._get_fov_size()
        # mode = Center(x=0, y=0, fov_width=fov_w, fov_height=fov_h)
        # self.fov_page.setValue(self._plate, mode)

    def _on_plate_changed(self, value: PlateInfo) -> None:
        self._plate = value.plate
        # update calibration page
        self._update_calibration_page(value.plate)
        # update fov page
        self._update_fov_page(value.plate)

    def _update_calibration_page(self, plate: WellPlate) -> None:
        """Update the calibration page with a new plate."""
        cal = self.calibration_page.value()
        # update only if the plate has changed
        if cal is not None and cal.plate != plate:
            self.calibration_page.setValue(_CalibrationData(plate=plate))

    def _update_fov_page(self, plate: WellPlate) -> None:
        """Update the fov page with a new plate."""
        fov_plate, mode = self.fov_page.value()
        # update only if the plate has changed
        if fov_plate != plate:
            fov_w, fov_h = self._get_fov_size()
            if mode is None:
                mode = Center(x=0, y=0, fov_width=fov_w, fov_height=fov_h)
            elif isinstance(mode, RandomPoints):
                max_width, max_height = plate.well_size
                # update the max_width and max_height with the new plate well size
                mode = mode.replace(
                    fov_height=fov_h,
                    fov_width=fov_w,
                    max_height=max_height * 1000,  # convert to um
                    max_width=max_width * 1000,  # convert to um
                    shape=ELLIPSE if plate.circular_wells else RECT,
                )
            else:
                mode = mode.replace(fov_height=fov_h, fov_width=fov_w)
            self.fov_page.setValue(self._plate, mode)

    def _on_sys_config_loaded(self) -> None:
        """Update the scene when the system configuration is loaded."""
        self._on_plate_changed(self.plate_page.value())

    def _on_px_size_changed(self) -> None:
        """Update the scene when the pixel size is changed."""
        plate, mode = self.fov_page.value()

        if plate is None:
            return

        # update the mode with the new fov size
        if mode is not None:
            fov_w, fov_h = self._get_fov_size()
            mode = mode.replace(fov_width=fov_w, fov_height=fov_h)

        # update the fov_page with the fov size
        self.fov_page.setValue(plate, mode)

    def _get_fov_size(self) -> tuple[float, float]:
        """Return the image size in µm depending on the camera device."""
        if (
            self._mmc is None
            or not self._mmc.getCameraDevice()
            or not self._mmc.getPixelSizeUm()
        ):
            return (0.0, 0.0)

        _cam_x = self._mmc.getImageWidth()
        _cam_y = self._mmc.getImageHeight()
        image_width = _cam_x * self._mmc.getPixelSizeUm()
        image_height = _cam_y * self._mmc.getPixelSizeUm()

        return image_width, image_height

    def _save(self) -> None:
        """Save the current wizard values as a json file."""
        (path, _) = QFileDialog.getSaveFileName(
            self, "Save the Wizard Configuration", "", "json(*.json)"
        )

        if not path:
            return

        value = self.value()

        if value is None:
            return

        Path(path).write_text(value.model_dump_json())

    def _load(self) -> None:
        """Load a .json wizard configuration."""
        (path, _) = QFileDialog.getOpenFileName(
            self, "Load a Wizard Configuration", "", "json(*.json)"
        )

        if not path:
            return

        with open(path) as file:
            self.setValue(WellPlatePlan(**json.load(file)))
