from __future__ import annotations

from pathlib import Path

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QFileDialog, QVBoxLayout, QWidget, QWizard, QWizardPage
from useq import WellPlatePlan

from pymmcore_widgets.useq_widgets import PointsPlanWidget, WellPlateWidget

from ._calibration_widget import PlateCalibrationWidget


class HCSWizard(QWizard):
    """A wizard to setup an High Content experiment.

    This widget can be used to select a plate, calibrate it, and then select the number
    of images (and their arrangement) to acquire per well.

    Parameters
    ----------
    parent : QWidget | None
        The parent widget. By default, None.
    mmcore : CMMCorePlus | None
        The CMMCorePlus instance. By default, None.
    """

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

        self.plate_page = _PlatePage(self)
        self.calibration_page = _PlateCalibrationPage(self._mmc, self)
        self.points_plan_page = _PointsPlanPage(self._mmc, self)

        self.addPage(self.plate_page)
        self.addPage(self.calibration_page)
        self.addPage(self.points_plan_page)

        # SAVE/LOAD BUTTONS ----------------------

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

        # CONNECTIONS ---------------------------

        self.plate_page.widget.valueChanged.connect(self._on_plate_changed)
        self._on_plate_changed(self.plate_page.widget.value())

    def _on_plate_changed(self, plate_plan: useq.WellPlatePlan) -> None:
        """Synchronize the points plan with the well size/shape."""
        pp_widget = self.points_plan_page.widget

        # set the well size on the points plan widget to the current plate well size
        well_width, well_height = plate_plan.plate.well_size
        pp_widget.setWellSize(well_width, well_height)

        # additionally, restrict the max width and height of the random points widget
        # to the plate size minus the fov size.
        fovw = pp_widget._selector.fov_w.value()
        fovh = pp_widget._selector.fov_h.value()

        # if the random points shape is a rectangle, but the wells are circular,
        # reduce the max width and height by 1.4 to keep the points inside the wells
        random_wdg = pp_widget.random_points_wdg
        if random_wdg.shape.currentText() == useq.Shape.RECTANGLE.value:
            if plate_plan.plate.circular_wells:
                well_width /= 1.4
                well_height /= 1.4

        random_wdg.max_width.setMaximum(well_width * 1000)
        random_wdg.max_width.setValue(well_width * 1000 - fovw / 1.4)
        random_wdg.max_height.setMaximum(well_height * 1000)
        random_wdg.max_height.setValue(well_height * 1000 - fovh / 1.4)

    def value(self) -> useq.WellPlatePlan:
        plate_plan = self.plate_page.widget.value()
        return useq.WellPlatePlan(
            plate=plate_plan.plate,
            selected_wells=plate_plan.selected_wells,
            rotation=self.field("rotation"),
            a1_center_xy=self.field("a1_center_xy"),
            well_points_plan=self.points_plan_page.widget.value(),
        )

    def setValue(self, value: useq.WellPlatePlan) -> None:
        self.plate_page.widget.setValue(value)
        # self.calibration_page.setValue(value.calibration)
        self.points_plan_page.widget.setValue(value.well_points_plan)

    def _save(self) -> None:
        """Save the current well plate plan to disk."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Well Plate Plan",
            "",
            "json(*.json)",
        )
        if path:
            Path(path).write_text(self.value().model_dump_json())

    def _load(self) -> None:
        """Load a well plate plan from disk."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Well Plate Plan",
            "",
            "json(*.json)",
        )
        if path:
            self.setValue(WellPlatePlan.from_file(path))


# ---------------------------------- PAGES ---------------------------------------


class _PlatePage(QWizardPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("Plate and Well Selection")

        self.widget = WellPlateWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)


class _PlateCalibrationPage(QWizardPage):
    def __init__(self, mmcore: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Plate Calibration")

        self.widget = PlateCalibrationWidget(mmcore=mmcore)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)


class _PointsPlanPage(QWizardPage):
    def __init__(self, mmcore: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mmc = mmcore
        self.setTitle("Field of View Selection")

        self.widget = PointsPlanWidget()
        self.widget._selector.fov_widgets.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)

        self._mmc.events.pixelSizeChanged.connect(self._on_px_size_changed)
        self._on_px_size_changed()

    def _on_px_size_changed(self) -> None:
        """Update the scene when the pixel size is changed."""
        val = self.widget.value()
        val.fov_width, val.fov_height = self._get_fov_size()
        self.widget.setValue(val)

    def _get_fov_size(self) -> tuple[float, float]:
        """Return the image size in µm depending on the camera device."""
        if self._mmc.getCameraDevice() and (px := self._mmc.getPixelSizeUm()):
            return self._mmc.getImageWidth() * px, self._mmc.getImageHeight() * px
        return (None, None)
