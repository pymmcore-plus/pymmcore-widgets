from __future__ import annotations

from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._util import SeparatorWidget
from pymmcore_widgets.hcs._well_calibration_widget import WellCalibrationWidget
from pymmcore_widgets.useq_widgets._well_plate_widget import WellPlateView

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus


class PlateCalibrationWidget(QWidget):
    calibrationChanged = Signal(bool)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        # mapping of well index (r, c) to well center (x, y)
        self._calibrated_wells: dict[tuple[int, int], tuple[float, float]] = {}

        # WIDGETS ------------------------------------------------------------

        self._plate_view = WellPlateView()
        self._plate_view.setDragMode(WellPlateView.DragMode.NoDrag)
        self._plate_view.setSelectionMode(WellPlateView.SelectionMode.SingleSelection)
        self._plate_view.setSelectedColor(Qt.GlobalColor.yellow)

        self._well_calibration_widget = WellCalibrationWidget()

        self._test_btn = QPushButton("Test Well")
        self._test_btn.setEnabled(False)

        # LAYOUT -------------------------------------------------------------

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(6, 0, 0, 0)
        self._well_calibration_widget.layout().setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._well_calibration_widget)
        right_layout.addWidget(SeparatorWidget())
        right_layout.addWidget(self._test_btn)
        right_layout.addStretch()

        layout = QHBoxLayout(self)
        layout.addWidget(self._plate_view)
        layout.addLayout(right_layout)

        # CONNECTIONS ---------------------------------------------------------

        self._plate_view.selectionChanged.connect(self._on_plate_selection_changed)
        self._well_calibration_widget.calibrationChanged.connect(
            self._on_well_calibration_changed
        )

    def setPlate(self, plate: str | useq.WellPlate | useq.WellPlatePlan) -> None:
        if isinstance(plate, str):
            plate = useq.WellPlate.from_str(plate)
        elif isinstance(plate, useq.WellPlatePlan):
            plate = plate.plate

        self._plate = plate
        self._plate_view.drawPlate(plate)
        self._well_calibration_widget.setCircularWell(plate.circular_wells)

    def _on_plate_selection_changed(self) -> None:
        if selected := self._plate_view.selectedIndices():
            idx = selected[0]
            well_name = self._plate.all_well_names[idx]
            self._well_calibration_widget.well_label.setText(well_name)
            if idx in self._calibrated_wells:
                self._well_calibration_widget.setWellCenter(self._calibrated_wells[idx])

    def _on_well_calibration_changed(self, calibrated: bool) -> None:
        self._test_btn.setEnabled(calibrated)
        if selected := self._plate_view.selectedIndices():
            idx = selected[0]
            if calibrated:
                self._calibrated_wells[idx] = self._well_calibration_widget.wellCenter()
                self._plate_view.setWellColor(*idx, Qt.GlobalColor.green)
            else:
                self._calibrated_wells.pop(idx, None)
                self._plate_view.setWellColor(*idx, None)
