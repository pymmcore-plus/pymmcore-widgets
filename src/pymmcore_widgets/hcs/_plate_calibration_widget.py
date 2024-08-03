from __future__ import annotations

from contextlib import suppress
from typing import Mapping

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStyle,
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

        self._info = QLabel("Please calibrate at least three wells.")
        self._info_icon = QLabel()

        # LAYOUT -------------------------------------------------------------

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.addWidget(self._calibration_widget_stack)
        right_layout.addWidget(SeparatorWidget())
        right_layout.addWidget(self._test_btn)
        right_layout.addStretch()

        top = QHBoxLayout()
        top.addWidget(self._plate_view, 1)
        top.addLayout(right_layout)

        info_layout = QHBoxLayout()
        mb_i = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self._info_icon.setPixmap(mb_i.pixmap(48))
        info_layout.addWidget(self._info_icon, 0)
        info_layout.addWidget(self._info, 1)

        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addLayout(info_layout)

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

    def platePlan(self) -> useq.WellPlatePlan:
        """Return the plate plan with calibration information."""
        a1_center_xy = (0.0, 0.0)
        rotation: float = 0.0
        if (osr := self._origin_spacing_rotation()) is not None:
            a1_center_xy, (unit_x, unit_y), rotation = osr
        return useq.WellPlatePlan(
            plate=self._current_plate,
            a1_center_xy=a1_center_xy,
            rotation=rotation,
        )

    # -----------------------------------------------

    def _origin_spacing_rotation(
        self,
    ) -> tuple[tuple[float, float], tuple[float, float], float] | None:
        """Return the origin, scale, and rotation of the plate.

        If the plate is not fully calibrated, returns None.

        The units are a little confusing here, but are chosen to match the units in
        the useq.WellPlatePlan class. The origin is in µm, the well spacing is in mm.

        Returns
        -------
        origin : tuple[float, float]
            The stage coordinates in µm of the center of well A1 (top-left corner).
        well_spacing : tuple[float, float]
            The center-to-center distance in mm (pitch) between wells in the x and y
            directions.
        rotation : float
                a1_center_xy : tuple[float, float]
            The rotation angle in degrees (anti-clockwise) of the plate.
        """
        if not len(self._calibrated_wells) >= self._min_wells_required:
            # not enough wells calibrated
            return None

        try:
            params = well_coords_affine(self._calibrated_wells)
        except ValueError:
            # collinear points
            return None

        a, b, ty, c, d, tx = params
        unit_y = np.hypot(a, c) / 1000  # convert to mm
        unit_x = np.hypot(b, d) / 1000  # convert to mm
        rotation = round(np.rad2deg(np.arctan2(c, a)), 2)

        return (tx, ty), (unit_x, unit_y), rotation

    def _get_or_create_well_calibration_widget(
        self, idx: tuple[int, int]
    ) -> WellCalibrationWidget:
        """Create or return the calibration widget for the given well index."""
        if not self._current_plate:
            raise ValueError("No plate set.")
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
        return self._calibration_widget_stack.currentWidget()  # type: ignore

    def _on_plate_selection_changed(self) -> None:
        """A well has been selected in the plate view."""
        if not (idx := self._selected_well_index()):
            return

        # create/activate a well calibration widget for the selected well
        with suppress(ValueError):
            well_calib_wdg = self._get_or_create_well_calibration_widget(idx)
            self._calibration_widget_stack.setCurrentWidget(well_calib_wdg)

        # enable/disable test button
        self._test_btn.setEnabled(idx in self._calibrated_wells)

    def _on_well_calibration_changed(self, calibrated: bool) -> None:
        """The current well calibration state has been changed."""
        self._test_btn.setEnabled(calibrated)
        if idx := self._selected_well_index():
            # update the color of the well in the plate view accordingly
            if calibrated and (well_calib_wdg := self._current_calibration_widget()):
                if center := well_calib_wdg.wellCenter():
                    self._calibrated_wells[idx] = center
                    self._plate_view.setWellColor(*idx, Qt.GlobalColor.green)
            else:
                self._calibrated_wells.pop(idx, None)
                self._plate_view.setWellColor(*idx, None)

        osr = self._origin_spacing_rotation()
        if fully_calibrated := (osr is not None):
            txt = "Plate is fully calibrated."
            origin, spacing, rotation = osr
            txt += f"\nA1 Center [µm]: ({origin[0]:.2f}, {origin[1]:.2f}),  "
            txt += f"Well Spacing [mm]: ({spacing[0]:.2f}, {spacing[1]:.2f}),  "
            txt += f"Rotation: {rotation}°"
            self._info.setText(txt)
            style = self.style()
            mb_i = style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
            self._info_icon.setPixmap(mb_i.pixmap(48))
        self.calibrationChanged.emit(fully_calibrated)

    def _selected_well_index(self) -> tuple[int, int] | None:
        if selected := self._plate_view.selectedIndices():
            return selected[0]
        return None


def well_coords_affine(
    index_coordinates: Mapping[tuple[int, int], tuple[float, float]],
) -> tuple[float, float, float, float, float, float]:
    """Return best-fit transformation that maps well plate indices to world coordinates.

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
    for (row, col), (x, y) in index_coordinates.items():
        # well plate indices go up in row as we go down in y
        # so we have to negate the row to get the correct transformation
        A.append([-row, col, 1, 0, 0, 0])
        A.append([0, 0, 0, -row, col, 1])
        # row corresponds to y, col corresponds to x
        B.extend((y, x))

    # Solve the least squares problem to find the affine transformation parameters
    params, _, rank, _ = np.linalg.lstsq(np.array(A), np.array(B), rcond=None)

    if rank != 6:
        raise ValueError("Underdetermined system of equations. Are points collinear?")

    return tuple(params)
