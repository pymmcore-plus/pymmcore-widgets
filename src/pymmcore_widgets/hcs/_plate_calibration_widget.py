from __future__ import annotations

from typing import Mapping

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._util import SeparatorWidget
from pymmcore_widgets.hcs._well_calibration_widget import WellCalibrationWidget
from pymmcore_widgets.useq_widgets._well_plate_widget import WellPlateView


class PlateCalibrationWidget(QWidget):
    """Widget to calibrate a well plate.

    Provides a view of the well plate with the ability to select and calibrate
    individual wells.
    """

    calibrationChanged = Signal(bool)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._current_plate: useq.WellPlate | None = None
        # minimum number of wells required to be calibrated
        # before the plate is considered calibrated
        self._min_wells_required: int = 2

        # mapping of well index (r, c) to well center (x, y)
        self._calibrated_wells: dict[tuple[int, int], tuple[float, float]] = {}

        # WIDGETS ------------------------------------------------------------

        self._plate_view = WellPlateView()
        self._plate_view.setDragMode(WellPlateView.DragMode.NoDrag)
        self._plate_view.setSelectionMode(WellPlateView.SelectionMode.SingleSelection)
        self._plate_view.setSelectedColor(Qt.GlobalColor.yellow)

        self._test_btn = QPushButton("Test Well")
        self._test_btn.setEnabled(False)

        # mapping of well index (r, c) to calibration widget
        # these are created on demand in _get_or_create_well_calibration_widget
        self._calibration_widgets: dict[tuple[int, int], WellCalibrationWidget] = {}
        self._calibration_widget_stack = QStackedWidget()

        # LAYOUT -------------------------------------------------------------

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.addWidget(self._calibration_widget_stack)
        right_layout.addWidget(SeparatorWidget())
        right_layout.addWidget(self._test_btn)
        right_layout.addStretch()

        layout = QHBoxLayout(self)
        layout.addWidget(self._plate_view, 1)
        layout.addLayout(right_layout)

        # CONNECTIONS ---------------------------------------------------------

        self._plate_view.selectionChanged.connect(self._on_plate_selection_changed)

    def setPlate(self, plate: str | useq.WellPlate | useq.WellPlatePlan) -> None:
        """Set the plate to be calibrated."""
        if isinstance(plate, str):
            plate = useq.WellPlate.from_str(plate)
        elif isinstance(plate, useq.WellPlatePlan):
            plate = plate.plate

        self._current_plate = plate
        self._plate_view.drawPlate(plate)

        # clear existing calibration widgets
        while self._calibration_widgets:
            wdg = self._calibration_widgets.popitem()[1]
            self._calibration_widget_stack.removeWidget(wdg)
            wdg.deleteLater()

        # Select A1 well
        self._plate_view.setSelectedIndices([(0, 0)])

    # -----------------------------------------------

    def _get_or_create_well_calibration_widget(
        self, idx: tuple[int, int]
    ) -> WellCalibrationWidget:
        """Create or return the calibration widget for the given well index."""
        if idx in self._calibration_widgets:
            return self._calibration_widgets[idx]

        self._calibration_widgets[idx] = wdg = WellCalibrationWidget(self, self._mmc)
        wdg.layout().setContentsMargins(0, 0, 0, 0)

        # set calibration widget well name, and circular well state
        well_name = self._current_plate.all_well_names[idx]
        wdg.well_label.setText(well_name)
        if self._current_plate:
            wdg.setCircularWell(self._current_plate.circular_wells)

        wdg.calibrationChanged.connect(self._on_well_calibration_changed)
        self._calibration_widget_stack.addWidget(wdg)
        return wdg

    def _current_calibration_widget(self) -> WellCalibrationWidget | None:
        return self._calibration_widget_stack.currentWidget()

    def _on_plate_selection_changed(self) -> None:
        """A well has been selected in the plate view."""
        if idx := self._selected_well_index():
            # create/activate a well calibration widget for the selected well
            well_calib_wdg = self._get_or_create_well_calibration_widget(idx)
            self._calibration_widget_stack.setCurrentWidget(well_calib_wdg)

        # enable/disable test button
        self._test_btn.setEnabled(idx in self._calibrated_wells)

    def _on_well_calibration_changed(self, calibrated: bool) -> None:
        """The current well calibration state has been changed."""
        self._test_btn.setEnabled(calibrated)
        if idx := self._selected_well_index():
            if calibrated and (well_calib_wdg := self._current_calibration_widget()):
                self._calibrated_wells[idx] = well_calib_wdg.wellCenter()
                self._plate_view.setWellColor(*idx, Qt.GlobalColor.green)
            else:
                self._calibrated_wells.pop(idx, None)
                self._plate_view.setWellColor(*idx, None)

        fully_calibrated = len(self._calibrated_wells) >= self._min_wells_required
        self.calibrationChanged.emit(fully_calibrated)
        if fully_calibrated:
            params = find_affine_transform(self._calibrated_wells)
            a, b, ty, c, d, tx = params
            # not quite right yet...
            _a1_center_xy = (tx, ty)
            _unit_y = np.hypot(a, c)
            _unit_x = np.hypot(b, d)
            _rotation = np.rad2deg(np.arctan2(c, a))

    def _selected_well_index(self) -> tuple[int, int] | None:
        if selected := self._plate_view.selectedIndices():
            return selected[0]
        return None


def find_affine_transform(
    index_coordinates: Mapping[tuple[int, int], tuple[float, float]],
) -> tuple[float, float, float, float, float, float]:
    """Return best-fit transformation that maps grid indices to world coordinates.

    Parameters
    ----------
    index_coordinates : Mapping[tuple[int, int], tuple[float, float]]
        A mapping of grid indices to world coordinates.

    Returns
    -------
    np.ndarray: The affine transformation matrix of shape (3, 3).
    """
    A: list[list[int]] = []
    B: list[float] = []
    for (row, col), (y, x) in index_coordinates.items():
        A.append([row, col, 1, 0, 0, 0])
        A.append([0, 0, 0, row, col, 1])
        B.extend((x, y))

    # Solve the least squares problem to find the affine transformation parameters
    params, _, _, _ = np.linalg.lstsq(np.array(A), np.array(B), rcond=None)
    return tuple(params)  # type: ignore [no-any-return]
