from __future__ import annotations

import math
import string
from pathlib import Path
from typing import Any, Iterable, List, NamedTuple, Optional, Tuple, Union, cast

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon, QPixmap
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from pymmcore_widgets.hcs._pydantic_model import FrozenModel
from pymmcore_widgets.useq_widgets._column_info import FloatColumn
from pymmcore_widgets.useq_widgets._data_table import DataTableWidget

from ._graphics_items import GREEN, RED, Well
from ._plate_model import Plate  # noqa: TCH001
from ._util import apply_rotation_matrix, get_well_center

AlignCenter = Qt.AlignmentFlag.AlignCenter
FixedSizePolicy = (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

ALPHABET = string.ascii_uppercase
ROLE = Qt.ItemDataRole.UserRole + 1

MAX = 9999999

ICON_PATH = Path(__file__).parent / "icons"
ICON_SIZE = 22

CIRCLE_ICON = QIcon(str(ICON_PATH / "circle-outline.svg"))
CIRCLE_TEXT = "3 points : add 3 points on the circonference of the well"
CIRCLE_MODE_POINTS = 3

SIDES_ICON = QIcon(str(ICON_PATH / "square-outline_s.svg"))
SIDES_ITEM = "4 points: add 4 points, 1 per side of the rectangular/square well"
SIDES_MODE_POINTS = 4

VERTICES_ICON = QIcon(str(ICON_PATH / "square-outline_v.svg"))
VERTICES_TEXT = (
    "2 points: add 2 points at 2 opposite vertices of the rectangular/square well"
)
VERTICES_MODE_POINTS = 2

LABEL_STYLE = """
    background: #00FF00;
    font-size: 16pt; font-weight:bold;
    color : black;
    border: 1px solid black;
    border-radius: 5px;
"""


class TwoPoints(NamedTuple):
    """Two vertices points to calibrate a rectangular/square well."""

    icon: QIcon = VERTICES_ICON
    text: str = VERTICES_TEXT
    points: int = VERTICES_MODE_POINTS


class ThreePoints(NamedTuple):
    """Three edge points to calibrate a circular well."""

    icon: QIcon = CIRCLE_ICON
    text: str = CIRCLE_TEXT
    points: int = CIRCLE_MODE_POINTS


class FourPoints(NamedTuple):
    """Four edge points to calibrate a rectangular/square well."""

    icon: QIcon = SIDES_ICON
    text: str = SIDES_ITEM
    points: int = SIDES_MODE_POINTS


class CalibrationData(FrozenModel):
    """Calibration data for the plate.

    Attributes
    ----------
    plate : Plate | None
        The plate to calibrate. By default, None.
    well_A1_center : tuple[float, float]
        The x and y stage coordinates of the center of well A1. By default, None.
    rotation_matrix : list | None
        The rotation matrix that should be used to correct any plate rortation, for
        for example:
            [
                [0.9954954725939522, 0.09480909262799544],
                [-0.09480909262799544, 0.9954954725939522]
            ]
        By default, None.
    calibration_position_a1 : list[tuple[float, float]]
        The x and y stage positions used to calibrate the well A1. By default, None.
    calibration_position_an : list[tuple[float, float]]
        The x and y stage positions used to calibrate the well An. By default, None.
    """

    plate: Optional[Plate] = None  # noqa: UP007
    well_A1_center: Optional[Tuple[float, float]] = None  # noqa: UP006, UP007
    rotation_matrix: Optional[List[List[float]]] = None  # noqa: UP006, UP007
    calibration_positions_a1: Optional[List[Tuple[float, float]]] = None  # noqa: UP006, UP007
    calibration_positions_an: Optional[List[Tuple[float, float]]] = None  # noqa: UP006, UP007


def find_circle_center(
    point1: tuple[float, float],
    point2: tuple[float, float],
    point3: tuple[float, float],
) -> tuple[float, float]:
    """
    Calculate the center of a circle passing through three given points.

    The function uses the formula for the circumcenter of a triangle to find
    the center of the circle that passes through the given points.
    """
    x1, y1 = point1
    x2, y2 = point2
    x3, y3 = point3

    # Calculate determinant D
    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

    # Calculate x and y coordinates of the circle's center
    x = (
        ((x1**2 + y1**2) * (y2 - y3))
        + ((x2**2 + y2**2) * (y3 - y1))
        + ((x3**2 + y3**2) * (y1 - y2))
    ) / D
    y = (
        ((x1**2 + y1**2) * (x3 - x2))
        + ((x2**2 + y2**2) * (x1 - x3))
        + ((x3**2 + y3**2) * (x2 - x1))
    ) / D

    return x, y


def find_rectangle_center(*args: tuple[float, ...]) -> tuple[float, float]:
    """
    Find the center of a rectangle/square well.

    ...given two opposite verices coordinates or 4 points on the edges.
    """
    x_list, y_list = list(zip(*args))

    if len(args) == 4:
        # get corner x and y coordinates
        x_list = (max(x_list), min(x_list))
        y_list = (max(y_list), min(y_list))

    # get center coordinates
    x = sum(x_list) / 2
    y = sum(y_list) / 2
    return x, y


def get_plate_rotation_matrix(
    xy_well_1: tuple[float, float], xy_well_2: tuple[float, float]
) -> list[list[float]]:
    """Get the rotation matrix to align the plate along the x axis."""
    x1, y1 = xy_well_1
    x2, y2 = xy_well_2

    m = (y2 - y1) / (x2 - x1)  # slope from y = mx + q
    plate_angle_rad = -np.arctan(m)
    # this is to test only, should be removed_____________________________
    # print(f"plate_angle: {np.rad2deg(plate_angle_rad)}")
    # ____________________________________________________________________
    return [
        [np.cos(plate_angle_rad), -np.sin(plate_angle_rad)],
        [np.sin(plate_angle_rad), np.cos(plate_angle_rad)],
    ]


def get_random_circle_edge_point(
    xc: float, yc: float, radius: float
) -> tuple[float, float]:
    """Get random edge point of a circle.

    ...with center (xc, yc) and radius `radius`.
    """
    # random angle
    angle = 2 * math.pi * np.random.random()
    # coordinates of the edge point using trigonometry
    x = radius * math.cos(angle) + xc
    y = radius * math.sin(angle) + yc

    return x, y


def get_random_rectangle_edge_point(
    xc: float, yc: float, well_size_x: float, well_size_y: float
) -> tuple[float, float]:
    """Get random edge point of a rectangle.

    ...with center (xc, yc) and size (well_size_x, well_size_y).
    """
    x_left, y_top = xc - (well_size_x / 2), yc + (well_size_y / 2)
    x_right, y_bottom = xc + (well_size_x / 2), yc - (well_size_y / 2)

    # random 4 edge points
    edge_points = [
        (x_left, np.random.uniform(y_top, y_bottom)),  # left
        (np.random.uniform(x_left, x_right), y_top),  # top
        (x_right, np.random.uniform(y_top, y_bottom)),  # right
        (np.random.uniform(x_left, x_right), y_bottom),  # bottom
    ]
    return edge_points[np.random.randint(0, 4)]


class _CalibrationModeWidget(QGroupBox):
    """Widget to select the calibration mode."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._mode_combo = QComboBox()
        self._mode_combo.setEditable(True)
        self._mode_combo.lineEdit().setReadOnly(True)
        self._mode_combo.lineEdit().setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._mode_combo.currentIndexChanged.connect(self._on_value_changed)

        lbl = QLabel(text="Calibration Mode:")
        lbl.setSizePolicy(*FixedSizePolicy)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(lbl)
        layout.addWidget(self._mode_combo)

    def _on_value_changed(self) -> None:
        """Emit the selected mode with valueChanged signal."""
        mode = self._mode_combo.itemData(self._mode_combo.currentIndex(), ROLE)
        self.valueChanged.emit(mode)

    def setValue(
        self, modes: list[ThreePoints | FourPoints | TwoPoints] | None
    ) -> None:
        """Set the available modes."""
        self._mode_combo.clear()
        if modes is None:
            return
        for idx, mode in enumerate(modes):
            self._mode_combo.addItem(mode.icon, mode.text)
            self._mode_combo.setItemData(idx, mode, ROLE)

    def value(self) -> ThreePoints | FourPoints | TwoPoints:
        """Return the selected calibration mode."""
        mode = self._mode_combo.itemData(self._mode_combo.currentIndex(), ROLE)
        return cast(Union[TwoPoints, ThreePoints, FourPoints], mode)


class _CalibrationTable(DataTableWidget):
    """Table to store the calibration positions."""

    X = FloatColumn(
        key="x", header="X [µm]", maximum=MAX, minimum=-MAX, is_row_selector=True
    )
    Y = FloatColumn(
        key="y", header="Y [µm]", maximum=MAX, minimum=-MAX, is_row_selector=True
    )

    def __init__(
        self,
        rows: int = 0,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(rows, parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        # QLabels to show the well name
        # fix policy of space already in the toolbar
        spacer = self.toolBar().layout().itemAt(0).widget()
        spacer.setFixedSize(5, ICON_SIZE)
        spacer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # label
        self._well_label = QLabel(text=" Well ")
        self._well_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._well_label.setFixedHeight(ICON_SIZE)
        self._well_label.setStyleSheet(LABEL_STYLE)
        self._well_label.setAlignment(AlignCenter)
        # spacer to keep the label to the left and the buttons to the right
        spacer_2 = QWidget()
        spacer_2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # add widgets to the toolbar
        self.toolBar().insertWidget(self.act_add_row, self._well_label)
        self.toolBar().insertWidget(self.act_add_row, spacer_2)

        # when a new row is inserted, call _on_rows_inserted
        # to update the new values from the core position
        self.table().model().rowsInserted.connect(self._on_rows_inserted)

    # _________________________PUBLIC METHODS_________________________ #

    def value(
        self, exclude_unchecked: bool = True, exclude_hidden_cols: bool = True
    ) -> list[tuple[float, float]] | None:
        """Get the calibration positions as a list of (x, y) tuples."""
        pos = [(r["x"], r["y"]) for r in self.table().iterRecords()]
        return pos or None

    def setValue(self, value: Iterable[tuple[float, float]]) -> None:
        """Set the calibration positions."""
        pos = [{self.X.key: x, self.Y.key: y} for x, y in value]
        super().setValue(pos)

    def setLabelText(self, text: str) -> None:
        """Set the well name."""
        self._well_label.setText(text)

    def getLabelText(self) -> str:
        """Return the well name."""
        return str(self._well_label.text())

    # _________________________PRIVATE METHODS________________________ #

    def _add_row(self) -> None:
        """Add a new to the end of the table and use the current core position."""
        # note: _add_row is only called when act_add_row is triggered
        # (e.g. when the + button is clicked). Not when a row is added programmatically

        # block the signal that's going to be emitted until _on_rows_inserted
        # has had a chance to update the values from the current stage position
        with signals_blocked(self):
            super()._add_row()
        self.valueChanged.emit()

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        with signals_blocked(self):
            for row_idx in range(start, end + 1):
                self._set_xy_from_core(row_idx)
        self.valueChanged.emit()

    def _set_xy_from_core(self, row: int, col: int = 0) -> None:
        if self._mmc.getXYStageDevice():
            data = {
                self.X.key: self._mmc.getXPosition(),
                self.Y.key: self._mmc.getYPosition(),
            }
            self.table().setRowData(row, data)


class _TestCalibrationWidget(QGroupBox):
    """Widget to test the calibration of a well.

    You can select a well and move the XY stage to a random edge point of the well.
    """

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self.setTitle("Test Calibration")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._plate: Plate | None = None

        # test calibration groupbox
        lbl = QLabel("Move to edge:")
        lbl.setSizePolicy(*FixedSizePolicy)
        # combo to select plate
        self._letter_combo = QComboBox()
        self._letter_combo.setEditable(True)
        self._letter_combo.lineEdit().setReadOnly(True)
        self._letter_combo.lineEdit().setAlignment(AlignCenter)
        self._letter_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        # combo to select well number
        self._number_combo = QComboBox()
        self._number_combo.setEditable(True)
        self._number_combo.lineEdit().setReadOnly(True)
        self._number_combo.lineEdit().setAlignment(AlignCenter)
        self._number_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        # test button
        self._test_button = QPushButton("Go")
        self._test_button.setEnabled(False)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setToolTip("Stop XY stage movement.")
        # groupbox
        test_calibration = QWidget()
        test_calibration_layout = QHBoxLayout(test_calibration)
        test_calibration_layout.setSpacing(10)
        test_calibration_layout.setContentsMargins(10, 10, 10, 10)
        test_calibration_layout.addWidget(lbl)
        test_calibration_layout.addWidget(self._letter_combo)
        test_calibration_layout.addWidget(self._number_combo)
        test_calibration_layout.addWidget(self._test_button)
        test_calibration_layout.addWidget(self._stop_button)

        # main
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(test_calibration)

        # connect
        self._stop_button.clicked.connect(self._stop_xy_stage)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> tuple[Plate | None, Well]:
        """Return the selected test well as `WellInfo` object."""
        return self._plate, Well(
            name=self._letter_combo.currentText() + self._number_combo.currentText(),
            row=self._letter_combo.currentIndex(),
            column=self._number_combo.currentIndex(),
        )

    def setValue(self, plate: Plate | None, well: Well | None) -> None:
        """Set the selected test well."""
        self._plate = plate
        self._update_combos()
        self._letter_combo.setCurrentIndex(0 if well is None else well.row)
        self._number_combo.setCurrentIndex(0 if well is None else well.column)

    # _________________________PRIVATE METHODS________________________ #

    def _stop_xy_stage(self) -> None:
        self._mmc.stop(self._mmc.getXYStageDevice())

    def _update_combos(self) -> None:
        if self._plate is None:
            return
        self._letter_combo.clear()
        letters = [ALPHABET[letter] for letter in range(self._plate.rows)]
        self._letter_combo.addItems(letters)
        self._letter_combo.adjustSize()

        self._number_combo.clear()
        numbers = [str(c) for c in range(1, self._plate.columns + 1)]
        self._number_combo.addItems(numbers)
        self._number_combo.adjustSize()


class _CalibrationLabel(QGroupBox):
    """Label to show the calibration status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Calibration Status")

        # icon
        self._icon_lbl = QLabel()
        self._icon_lbl.setSizePolicy(*FixedSizePolicy)
        self._icon_lbl.setPixmap(
            icon(MDI6.close_octagon_outline, color=RED).pixmap(QSize(30, 30))
        )
        # text
        self._text_lbl = QLabel(text="Plate Not Calibrated!")
        self._text_lbl.setStyleSheet("font-size: 14px; font-weight: bold;")

        # main
        layout = QHBoxLayout(self)
        layout.setAlignment(AlignCenter)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> str:
        return str(self._text_lbl.text())

    def setValue(self, pixmap: QPixmap, text: str) -> None:
        """Set the icon and text of the labels."""
        self._icon_lbl.setPixmap(pixmap)
        self._text_lbl.setText(text)


class PlateCalibrationWidget(QWidget):
    """Widget to calibrate the sample plate.

    Attributes
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
        self._plate: Plate | None = None

        self._calibration_data: CalibrationData | None = None

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
        self._calibrate_button = QPushButton(text="Calibrate Plate")
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

    def value(self) -> CalibrationData | None:
        """Return the calibration data."""
        return self._calibration_data

    def setValue(self, value: CalibrationData | None) -> None:
        """Set the calibration data."""
        # reset calibration state
        self._reset_calibration()

        self._calibration_data = value

        self._plate = value.plate if value is not None else None

        # set calibration mode
        calibration_mode: list[TwoPoints | ThreePoints | FourPoints] | None = (
            None
            if self._plate is None
            else (
                [ThreePoints()] if self._plate.circular else [TwoPoints(), FourPoints()]
            )
        )
        self._calibration_mode.setValue(calibration_mode)

        # update calibration tables
        pos_a1 = value.calibration_positions_a1 if value is not None else None
        pos_an = value.calibration_positions_an if value is not None else None
        self._update_tables(self._plate, pos_a1, pos_an)

        # update test calibration
        self._test_calibration.setValue(plate=self._plate, well=None)

    # _________________________PRIVATE METHODS________________________ #

    def _update_tables(
        self,
        plate: Plate | None,
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
        self._calibration_data = CalibrationData(plate=self._plate)

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
            return

        # get calibration well centers
        a1_center, an_center = self._find_wells_center()

        # return if any of the necessary well centers is None
        if None in a1_center or (None in an_center and self._plate.columns > 1):
            self._reset_calibration()
            return

        a1_center = cast(Tuple[float, float], a1_center)

        # get plate rotation matrix
        if None in an_center:
            rotation_matrix = None
        else:
            an_center = cast(Tuple[float, float], an_center)
            rotation_matrix = get_plate_rotation_matrix(a1_center, an_center)

        # set calibration_info property
        pos_a1 = self._table_a1.value()
        pos_an = self._table_an.value() if self._plate.columns > 1 else None
        self._calibration_data = CalibrationData(
            plate=self._plate,
            well_A1_center=a1_center,
            rotation_matrix=rotation_matrix,
            calibration_positions_a1=pos_a1,
            calibration_positions_an=pos_an,
        )

        # update calibration label
        self._set_calibration_label(True)
        self._test_calibration._test_button.setEnabled(True)

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
        """Find the center given 2, 3 or 4 points depending on the well shape."""
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

        return (
            find_circle_center(*pos)
            if expected_num_pos == CIRCLE_MODE_POINTS
            else find_rectangle_center(*pos)
        )

    def _move_to_well_edge(self) -> None:
        """Move to the edge of the selected well to test the calibratiion."""
        if self._plate is None:
            return

        data = self._calibration_data
        if data is None or data.well_A1_center is None:
            return

        _, well = self._test_calibration.value()
        a1_x, a1_y = data.well_A1_center
        cx, cy = get_well_center(self._plate, well, a1_x, a1_y)

        if data.rotation_matrix is not None:
            cx, cy = apply_rotation_matrix(data.rotation_matrix, a1_x, a1_y, cx, cy)

        self._mmc.waitForDevice(self._mmc.getXYStageDevice())

        if self._plate.circular:
            x, y = get_random_circle_edge_point(
                cx, cy, self._plate.well_size_x * 1000 / 2
            )
        else:
            x, y = get_random_rectangle_edge_point(
                cx, cy, self._plate.well_size_x * 1000, self._plate.well_size_y * 1000
            )

        self._mmc.setXYPosition(x, y)
