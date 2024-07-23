from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import (
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from pymmcore_widgets.hcs._calibration_widget._calibration_widget import (
    _CalibrationData,
    _PlateCalibrationWidget,
)
from pymmcore_widgets.hcs._fov_widget._fov_widget import _FOVSelectorWidget
from pymmcore_widgets.hcs._plate_widget import PlateInfo, _PlateSelectorWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from useq import GridRowsColumns, RandomPoints, WellPlate

    from pymmcore_widgets.hcs._fov_widget._fov_sub_widgets import Center

EXPANDING = (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class PlatePage(QWizardPage):
    """The wizard page to select a plate and the wells to image."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setTitle("Plate and Well Selection")

        self._plate_widget = _PlateSelectorWidget()

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._plate_widget)

        self.setButtonText(QWizard.WizardButton.NextButton, "Calibration >")

        self.combo = self._plate_widget.plate_combo

    def value(self) -> PlateInfo:
        """Return the selected well plate and the selected wells."""
        return self._plate_widget.value()

    def setValue(self, value: PlateInfo) -> None:
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


class FOVSelectorPage(QWizardPage):
    """The wizard page to select the FOVs per well."""

    def __init__(
        self,
        parent: QWidget | None = None,
        plate: WellPlate | None = None,
        mode: Center | RandomPoints | GridRowsColumns | None = None,
    ) -> None:
        super().__init__(parent)
        self.setTitle("Field of View Selection")

        self._fov_widget = _FOVSelectorWidget(plate, mode, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._fov_widget)
        layout.addItem(QSpacerItem(0, 0, *EXPANDING))

        self.setButtonText(QWizard.WizardButton.FinishButton, "Value")

    def value(
        self,
    ) -> tuple[WellPlate | None, Center | RandomPoints | GridRowsColumns | None]:
        """Return the list of FOVs."""
        return self._fov_widget.value()

    def setValue(
        self,
        plate: WellPlate | None,
        mode: Center | RandomPoints | GridRowsColumns | None,
    ) -> None:
        """Set the list of FOVs."""
        self._fov_widget.setValue(plate, mode)
