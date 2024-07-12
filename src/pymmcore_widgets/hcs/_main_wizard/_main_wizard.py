from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)
from useq import WellPlatePlan

from pymmcore_widgets.hcs._calibration_widget._calibration_widget import (
    _CalibrationData,
    _PlateCalibrationWidget,
)
from pymmcore_widgets.useq_widgets import WellPlateWidget
from pymmcore_widgets.useq_widgets.points_plans._points_plan_widget import (
    PointsPlanWidget,
)


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

        # WIZARD PAGES ----------------------
        self.plate_page = PlatePage(self)
        # self.calibration_page = PlateCalibrationPage(self, self._mmc)
        self.fov_page = PointsPlanPage(self._mmc, self)

        self.addPage(self.plate_page)
        # self.addPage(self.calibration_page)
        self.addPage(self.fov_page)

        # BUTTONS ----------------------

        # add custom button to save
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        save_btn = self.button(QWizard.WizardButton.CustomButton1)
        save_btn.setText("Save")
        save_btn.clicked.connect(self._save)
        self.setButton(QWizard.WizardButton.CustomButton1, save_btn)
        # add custom button to load
        self.setOption(QWizard.WizardOption.HaveCustomButton2, True)
        load_btn = self.button(QWizard.WizardButton.CustomButton2)
        load_btn.setText("Load")
        load_btn.clicked.connect(self._load)
        self.setButton(QWizard.WizardButton.CustomButton2, load_btn)

        self.setOption(QWizard.WizardOption.HaveCustomButton3, True)
        print_val = self.button(QWizard.WizardButton.CustomButton3)
        print_val.setText("Print")
        from rich import print

        print_val.clicked.connect(lambda: print(self.value()))
        self.setButton(QWizard.WizardButton.CustomButton3, print_val)

        # LAYOUT ------------------------------------------

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 50, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # _________________________PUBLIC METHODS_________________________ #

    def accept(self) -> None:
        """Emit the valueChanged signal when the wizard is accepted."""
        self.valueChanged.emit(self.value())

    # _________________________PRIVATE METHODS_________________________ #

    def value(self) -> useq.WellPlatePlan:
        pp = self.plate_page.value()
        print(self.fov_page.value())
        return pp.model_copy(
            update={
                "well_points_plan": self.fov_page.value(),
                "rotation": self.field("rotation"),
                "a1_center_xy": self.field("a1_center_xy"),
            }
        )

    def setValue(self, value: useq.WellPlatePlan) -> None:
        self.plate_page.setValue(value)
        # self.calibration_page.setValue(value.calibration)
        self.fov_page.setValue(value.well_points_plan)

    def _save(self) -> None:
        """Save the current wizard values as a json file."""
        (path, _) = QFileDialog.getSaveFileName(
            self, "Save the Wizard Configuration", "", "json(*.json)"
        )

        if not path:
            return

        Path(path).write_text(self.value().model_dump_json())

    def _load(self) -> None:
        """Load a .json wizard configuration."""
        (path, _) = QFileDialog.getOpenFileName(
            self,
            "Load a Wizard Configuration",
            "",
            "json(*.json)",
        )

        if not path:
            return

        self.setValue(WellPlatePlan.from_file(path))


if TYPE_CHECKING:
    import useq


EXPANDING = (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class PlatePage(QWizardPage):
    """The wizard page to select a plate and the wells to image."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setTitle("Plate and Well Selection")

        self._plate_widget = WellPlateWidget()

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._plate_widget)

        self.setButtonText(QWizard.WizardButton.NextButton, "Calibration >")

    def value(self) -> useq.WellPlatePlan:
        """Return the selected well plate and the selected wells."""
        return self._plate_widget.value()

    def setValue(self, value: useq.WellPlatePlan | Any) -> None:
        """Set the current plate and the selected wells.

        `value` is a list of (well_name, row, column).
        """
        self._plate_widget.setValue(value)


class PlateCalibrationPage(QWizardPage):
    """The wizard page to calibrate the plate."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self.setTitle("Plate Calibration")

        self._calibration = _PlateCalibrationWidget(mmcore=mmcore)
        self.registerField("rotation", self._calibration, "rotation")
        self.registerField("a1_center_xy", self._calibration, "a1_center_xy")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._calibration)
        layout.addItem(QSpacerItem(0, 0, *EXPANDING))

        self.setButtonText(QWizard.WizardButton.NextButton, "FOVs >")

    def value(self) -> _CalibrationData | None:
        """Return the calibration info."""
        return self._calibration.value()

    def setValue(self, value: _CalibrationData | None) -> None:
        """Set the calibration info."""
        self._calibration.setValue(value)

    def isCalibrated(self) -> bool:
        """Return True if the plate is calibrated."""
        return self._calibration.isCalibrated()


class PointsPlanPage(QWizardPage):
    """The wizard page to select the FOVs per well."""

    def __init__(
        self,
        mmcore: CMMCorePlus,
        parent: QWidget | None = None,
        plan: useq.RelativeMultiPointPlan | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore
        self.setTitle("Field of View Selection")

        self._fov_widget = PointsPlanWidget(plan, parent=self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._fov_widget)
        layout.addItem(QSpacerItem(0, 0, *EXPANDING))

        self.setButtonText(QWizard.WizardButton.FinishButton, "Value")
        self._mmc.events.pixelSizeChanged.connect(self._on_px_size_changed)

    def value(self) -> useq.RelativeMultiPointPlan:
        """Return the list of FOVs."""
        return self._fov_widget.value()

    def setValue(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Set the list of FOVs."""
        self._fov_widget.setValue(plan)

    def _on_px_size_changed(self) -> None:
        """Update the scene when the pixel size is changed."""
        plate, mode = self.value()

        # if plate is None:
        #     return

        # # update the mode with the new fov size
        # if mode is not None:
        #     fov_w, fov_h = self._get_fov_size()
        #     mode = mode.replace(fov_width=fov_w, fov_height=fov_h)

        # # update the fov_page with the fov size
        # self.setValue(plate, mode)

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
