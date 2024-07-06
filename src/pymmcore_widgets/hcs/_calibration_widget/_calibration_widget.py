from __future__ import annotations

from pathlib import Path
from typing import (
    ClassVar,
    NamedTuple,
    Tuple,
    cast,
)

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from useq import WellPlate  # noqa: TCH002

from pymmcore_widgets.hcs._graphics_items import GREEN, RED
from pymmcore_widgets.hcs._util import (
    apply_rotation_matrix,
    get_well_center,
)

from ._calibration_sub_widgets import (
    Mode,
    _CalibrationLabel,
    _CalibrationModeWidget,
    _CalibrationTable,
    _TestCalibrationWidget,
)
from ._util import (
    find_circle_center,
    find_rectangle_center,
    get_plate_rotation_angle,
    get_random_circle_edge_point,
    get_random_rectangle_edge_point,
)

ICON_PATH = Path(__file__).parent / "icons"
CIRCLE_CENTER_POINTS: int = 1
CIRCLE_EDGES_POINTS: int = 3


class _CalibrationData(NamedTuple):
    """Calibration data for the plate.

    Attributes
    ----------
    calibrated : bool
        True if the plate is calibrated, False otherwise.
    plate : WellPlate | None
        The plate to calibrate.
    well_A1_center : tuple[float, float]
        The x and y stage coordinates of the center of well A1.
    rotation : float
        The rotation angle that should be used to correct any plate rortation
    calibration_position_a1 : list[tuple[float, float]]
        The x and y stage positions used to calibrate the well A1.
    calibration_position_an : Optional[list[tuple[float, float]]]
        The x and y stage positions used to calibrate the well An. By default, an empty
        list.
    """

    plate: WellPlate
    calibrated: bool = False
    a1_center_xy: tuple[float, float] | None = None
    rotation: float = 0.0
    calibration_positions_a1: ClassVar[list[tuple[float, float]]] = []
    calibration_positions_an: ClassVar[list[tuple[float, float]]] = []


class _PlateCalibrationWidget(QWidget):
    """Widget to calibrate the sample plate.

    Attributes
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

        self.MODES: dict[bool, list[Mode]] = {
            True: [
                Mode(
                    "1 points : add 1 points at the center of the well",
                    CIRCLE_CENTER_POINTS,
                    QIcon(str(ICON_PATH / "circle-center.svg")),
                ),
                Mode(
                    "3 points : add 3 points at the edges of the well",
                    CIRCLE_EDGES_POINTS,
                    QIcon(str(ICON_PATH / "circle-edges.svg")),
                ),
            ],
            False: [
                Mode(
                    "2 points : add 2 points at the center of the well",
                    2,
                    QIcon(str(ICON_PATH / "square-vertices.svg")),
                ),
                Mode(
                    "4 points : add 4 points at the edges of the well",
                    4,
                    QIcon(str(ICON_PATH / "square-edges.svg")),
                ),
            ],
        }

        self._plate: WellPlate | None = None

        self._calibration_data: _CalibrationData | None = None

        # calibration mode
        self._calibration_mode = _CalibrationModeWidget()

        # calibration tables
        self._table_a1 = _CalibrationTable()
        self._table_an = _CalibrationTable()
        table_group = QGroupBox()
        table_group_layout = QHBoxLayout(table_group)
        table_group_layout.setContentsMargins(0, 0, 0, 0)
        table_group_layout.setSpacing(10)
        table_group_layout.addWidget(self._table_a1)
        table_group_layout.addWidget(self._table_an)
        # calibration buttons
        self._calibrate_button = QPushButton(text="Calibrate WellPlate")
        self._calibrate_button.setIcon(icon(MDI6.target_variant, color="darkgrey"))
        self._calibrate_button.setIconSize(QSize(30, 30))
        spacer = QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        calibrate_btn_wdg = QWidget()
        calibrate_btn_wdg_layout = QHBoxLayout(calibrate_btn_wdg)
        calibrate_btn_wdg_layout.setSpacing(10)
        calibrate_btn_wdg_layout.setContentsMargins(0, 0, 0, 0)
        calibrate_btn_wdg_layout.addItem(spacer)
        calibrate_btn_wdg_layout.addWidget(self._calibrate_button)
        # calibration tabls and calibration button group
        table_and_btn_wdg = QGroupBox()
        table_and_btn_wdg_layout = QVBoxLayout(table_and_btn_wdg)
        table_and_btn_wdg_layout.setSpacing(10)
        table_and_btn_wdg_layout.setContentsMargins(10, 10, 10, 10)
        table_and_btn_wdg_layout.addWidget(table_group)
        table_and_btn_wdg_layout.addWidget(calibrate_btn_wdg)

        # test calibration
        self._test_calibration = _TestCalibrationWidget()
        # calibration label
        self._calibration_label = _CalibrationLabel()
        # test calibration and calibration label group
        bottom_group = QWidget()
        bottom_group_layout = QHBoxLayout(bottom_group)
        bottom_group_layout.setSpacing(10)
        bottom_group_layout.setContentsMargins(10, 10, 10, 10)
        bottom_group_layout.addWidget(self._test_calibration)
        bottom_group_layout.addWidget(self._calibration_label)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        main_layout.addWidget(self._calibration_mode)
        main_layout.addWidget(table_and_btn_wdg)
        main_layout.addWidget(bottom_group)

        # connect
        self._calibrate_button.clicked.connect(self._on_calibrate_button_clicked)
        self._test_calibration._test_button.clicked.connect(self._move_to_well_edge)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> _CalibrationData | None:
        """Return the calibration data."""
        return self._calibration_data

    def setValue(self, value: _CalibrationData | None) -> None:
        """Set the calibration data."""
        # reset calibration state
        self._reset_calibration()

        self._calibration_data = value

        self._plate = value.plate if value is not None else None

        # set calibration mode
        calibration_mode = (
            self.MODES[self._plate.circular_wells] if self._plate is not None else None
        )

        self._calibration_mode.setValue(calibration_mode)

        # update calibration tables
        pos_a1 = value.calibration_positions_a1 if value is not None else None
        pos_an = value.calibration_positions_an if value is not None else None
        self._update_tables(self._plate, pos_a1, pos_an)

        # update test calibration
        self._test_calibration.setValue(plate=self._plate, well=None)

        if value is not None and value.calibrated:
            self._set_calibration_label(True)
            self._test_calibration._test_button.setEnabled(True)

    def isCalibrated(self) -> bool:
        """Return True if the plate is calibrated, False otherwise."""
        return self._calibration_data is not None and self._calibration_data.calibrated

    # _________________________PRIVATE METHODS________________________ #

    def _update_tables(
        self,
        plate: WellPlate | None,
        pos_a1: list[tuple[float, float]] | None,
        pos_an: list[tuple[float, float]] | None,
    ) -> None:
        """Update the calibration tables."""
        # set table values
        self._table_a1.setValue([] if pos_a1 is None else pos_a1)
        self._table_an.setValue([] if pos_an is None else pos_an)

        # set table well name
        a1 = "" if plate is None else " Well A1 "
        an = "" if plate is None else f" Well A{plate.columns} "
        self._table_a1.setLabelText(a1)
        self._table_an.setLabelText(an)

        # hide an table if plate has only one column
        self._table_a1.show() if plate is not None else self._table_a1.hide()
        (
            self._table_an.show()
            if plate is not None and plate.columns > 1
            else self._table_an.hide()
        )

    def _reset_calibration(self) -> None:
        """Reset to not calibrated state."""
        self._set_calibration_label(False)
        self._test_calibration._test_button.setEnabled(False)
        self._calibration_data = None

    def _set_calibration_label(self, state: bool) -> None:
        """Set the calibration label."""
        lbl_icon = MDI6.check_bold if state else MDI6.close_octagon_outline
        lbl_icon_size = QSize(20, 20) if state else QSize(30, 30)
        lbl_icon_color = GREEN if state else RED
        text = "Plate Calibrated!" if state else "Plate Not Calibrated!"
        self._calibration_label.setValue(
            pixmap=icon(lbl_icon, color=lbl_icon_color).pixmap(lbl_icon_size),
            text=text,
        )

    def _on_calibrate_button_clicked(self) -> None:
        """Calibrate the plate."""
        if self._plate is None:
            self._reset_calibration()
            self.valueChanged.emit(self.value())
            return

        # get calibration well centers
        a1_center, an_center = self._find_wells_center()

        # return if any of the necessary well centers is None
        if None in a1_center or (None in an_center and self._plate.columns > 1):
            self._reset_calibration()
            self.valueChanged.emit(self.value())
            return

        a1_center = cast(Tuple[float, float], a1_center)

        # get plate rotation matrix
        if None in an_center:
            rotation = 0.0
        else:
            an_center = cast(Tuple[float, float], an_center)
            rotation = get_plate_rotation_angle(a1_center, an_center)

        # set calibration_info property
        pos_a1 = self._table_a1.value()
        pos_an = self._table_an.value() if self._plate.columns > 1 else []
        self._calibration_data = _CalibrationData(
            plate=self._plate,
            calibrated=True,
            a1_center_xy=a1_center,
            rotation=rotation,
            calibration_positions_a1=pos_a1,
            calibration_positions_an=pos_an,
        )

        # update calibration label
        self._set_calibration_label(True)
        self._test_calibration._test_button.setEnabled(True)

        self.valueChanged.emit(self.value())

    def _find_wells_center(
        self,
    ) -> tuple[tuple[float | None, float | None], tuple[float | None, float | None]]:
        """Find the centers in stage coordinates of the calibration wells."""
        if self._plate is None:
            return (None, None), (None, None)

        a1_x, a1_y = self._find_center(self._table_a1)
        if a1_x is None or a1_y is None:
            return (None, None), (None, None)

        an_x, an_y = (
            self._find_center(self._table_an)
            if self._plate.columns > 1
            else (None, None)
        )
        return (a1_x, a1_y), (an_x, an_y)

    def _find_center(
        self, table: _CalibrationTable
    ) -> tuple[float | None, float | None]:
        """Find the center given 1, 2, 3 or 4 points depending on the well shape."""
        pos = table.value()

        if pos is None:
            return None, None

        num_pos = len(pos) if pos is not None else 0
        expected_num_pos = self._calibration_mode.value().points
        well_name = table._well_label.text().replace(" ", "")

        # check if the number of points is correct
        if num_pos != expected_num_pos:
            self._reset_calibration()
            QMessageBox.critical(
                self,
                "Error",
                f"Invalid number of positions for '{well_name}'. "
                f"Expected {expected_num_pos}, got {num_pos or 0}.",
            )
            return None, None

        if expected_num_pos == CIRCLE_CENTER_POINTS:
            return pos[0]

        return (
            find_circle_center(*pos)
            if expected_num_pos == CIRCLE_EDGES_POINTS
            else find_rectangle_center(*pos)
        )

    def _deg_to_matrix(self, angle: float) -> np.ndarray:
        """Convert rotation (which is in degrees) to a rotation matrix."""
        rads = np.radians(angle)
        return np.array([[np.cos(rads), -np.sin(rads)], [np.sin(rads), np.cos(rads)]])

    def _move_to_well_edge(self) -> None:
        """Move to the edge of the selected well to test the calibratiion."""
        if self._plate is None:
            return

        data = self._calibration_data
        if data is None or data.a1_center_xy is None:
            return

        _, well = self._test_calibration.value()
        a1_x, a1_y = data.a1_center_xy
        cx, cy = get_well_center(self._plate, well, a1_x, a1_y)

        if data.rotation:
            rotation_matrix = self._deg_to_matrix(data.rotation)
            cx, cy = apply_rotation_matrix(rotation_matrix, a1_x, a1_y, cx, cy)

        self._mmc.waitForDevice(self._mmc.getXYStageDevice())

        well_size_x, well_size_y = self._plate.well_size
        if self._plate.circular_wells:
            x, y = get_random_circle_edge_point(cx, cy, well_size_x * 1000 / 2)
        else:
            x, y = get_random_rectangle_edge_point(
                cx, cy, well_size_x * 1000, well_size_y * 1000
            )

        self._mmc.setXYPosition(x, y)
