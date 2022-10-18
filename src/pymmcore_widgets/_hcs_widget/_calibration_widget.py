import string
from pathlib import Path
from typing import List, Optional, Tuple, overload

import numpy as np
import yaml  # type: ignore
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from pymmcore_plus._logger import logger
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked
from sympy import Eq, solve, symbols

PLATE_DATABASE = Path(__file__).parent / "_well_plate.yaml"
ALPHABET = string.ascii_uppercase


class PlateCalibration(QWidget):
    """Widget to calibrate the sample plate."""

    PlateFromCalibration = Signal(tuple)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.plate = None
        self.A1_well: Tuple[str, float, float] = ()  # type: ignore
        self.plate_rotation_matrix: np.ndarray = None  # type: ignore
        self.plate_angle_deg: float = 0.0
        self.is_calibrated = False

        self._create_gui()

    def _create_gui(self) -> None:

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.info_lbl = QLabel()
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.layout().addWidget(self.info_lbl)

        wdg = QWidget()
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(5)
        wdg.setLayout(mode_layout)
        lbl = QLabel(text="Wells for the calibration:")
        lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self._calibration_combo = QComboBox()
        self._calibration_combo.addItems(["1 Well (A1)"])
        self._calibration_combo.currentTextChanged.connect(self._on_combo_changed)
        mode_layout.addWidget(lbl)
        mode_layout.addWidget(self._calibration_combo)
        self.layout().addWidget(wdg)

        group = QGroupBox()
        self.group_layout = QVBoxLayout()
        self.group_layout.setSpacing(15)
        self.group_layout.setContentsMargins(0, 0, 0, 0)
        group.setLayout(self.group_layout)
        layout.addWidget(group)
        self._create_tables(n_tables=1)

        bottom_group = QGroupBox()
        bottom_group_layout = QHBoxLayout()
        bottom_group_layout.setSpacing(10)
        bottom_group_layout.setContentsMargins(10, 10, 10, 10)
        bottom_group.setLayout(bottom_group_layout)

        cal_state_wdg = QWidget()
        cal_state_wdg_layout = QHBoxLayout()
        cal_state_wdg_layout.setAlignment(Qt.AlignCenter)
        cal_state_wdg_layout.setSpacing(0)
        cal_state_wdg_layout.setContentsMargins(0, 0, 0, 0)
        cal_state_wdg.setLayout(cal_state_wdg_layout)
        self.icon_lbl = QLabel()
        self.icon_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.icon_lbl.setPixmap(
            icon(MDI6.close_octagon_outline, color="magenta").pixmap(QSize(30, 30))
        )
        self.cal_lbl = QLabel()
        self.cal_lbl.setText("Plate non Calibrated!")
        cal_state_wdg_layout.addWidget(self.icon_lbl)
        cal_state_wdg_layout.addWidget(self.cal_lbl)

        calibrate_btn = QPushButton(text="Calibrate Plate")
        calibrate_btn.clicked.connect(self._calibrate_plate)

        bottom_group_layout.addWidget(calibrate_btn)
        bottom_group_layout.addWidget(cal_state_wdg)

        layout.addWidget(bottom_group)

    def _load_plate_info(self) -> dict:
        with open(
            PLATE_DATABASE,
        ) as file:
            return yaml.safe_load(file)  # type: ignore

    def _create_tables(self, n_tables: int) -> None:
        self.table_1 = CalibrationTable()
        self.table_2 = CalibrationTable()
        self.group_layout.addWidget(self.table_1)
        self.group_layout.addWidget(self.table_2)

        self._show_hide_tables(n_tables)

    def _show_hide_tables(
        self, n_tables: int, well_list: List[str] = None  # type: ignore
    ) -> None:

        self.table_1._rename_well_column("Well A1")
        self.table_1.show()

        if n_tables == 1:
            self.table_2.hide()

        else:
            if well_list:
                self.table_2._rename_well_column(f"Well {well_list[0]}")
            self.table_2.show()

    def _clear_tables(self) -> None:
        self.table_1._clear_table()
        self.table_2._clear_table()

    def _on_combo_changed(self, text: str) -> None:
        if not self.plate:
            return
        self._update_gui(self.plate.get("id"), from_combo=text)

        # only to test
        # self.table_1.tb.setRowCount(3)
        # self.table_2.tb.setRowCount(3)
        # # a1
        # self.table_1.tb.setItem(0, 0, QTableWidgetItem("Well A1_pos000"))
        # self.table_1.tb.setItem(0, 1, QTableWidgetItem("-50"))
        # self.table_1.tb.setItem(0, 2, QTableWidgetItem("0"))
        # self.table_1.tb.setItem(1, 0, QTableWidgetItem("Well A1_pos001"))
        # self.table_1.tb.setItem(1, 1, QTableWidgetItem("0"))
        # self.table_1.tb.setItem(1, 2, QTableWidgetItem("50"))
        # self.table_1.tb.setItem(2, 0, QTableWidgetItem("Well A1_pos002"))
        # self.table_1.tb.setItem(2, 1, QTableWidgetItem("50"))
        # self.table_1.tb.setItem(2, 2, QTableWidgetItem("0"))
        # # an
        # self.table_2.tb.setItem(0, 0, QTableWidgetItem("Well A3_pos000"))
        # self.table_2.tb.setItem(0, 1, QTableWidgetItem("1364.213562373095"))
        # self.table_2.tb.setItem(0, 2, QTableWidgetItem("1414.2135623730949"))
        # self.table_2.tb.setItem(1, 0, QTableWidgetItem("Well A3_pos001"))
        # self.table_2.tb.setItem(1, 1, QTableWidgetItem("1414.213562373095"))
        # self.table_2.tb.setItem(1, 2, QTableWidgetItem("1364.2135623730949"))
        # self.table_2.tb.setItem(2, 0, QTableWidgetItem("Well A3_pos002"))
        # self.table_2.tb.setItem(2, 1, QTableWidgetItem("1464.213562373095"))
        # self.table_2.tb.setItem(2, 2, QTableWidgetItem("1414.2135623730949"))

    def _update_gui(self, plate: str, from_combo: str = "") -> None:

        if self.plate and self.plate.get("id") == plate and not from_combo:
            return

        self._set_calibrated(False)
        self._clear_tables()

        try:
            self.plate = self._load_plate_info()[plate]
        except KeyError:
            self.plate = None
            return

        with signals_blocked(self._calibration_combo):
            self._calibration_combo.clear()

            rows = self.plate.get("rows")  # type: ignore
            cols = self.plate.get("cols")  # type: ignore
            well = ALPHABET[rows - 1]

            well_list = []

            if self.plate.get("id") == "_from calibration":  # type: ignore
                self._calibration_combo.addItem("1 Well (A1)")

            elif rows == 1:
                if cols == 1:
                    self._calibration_combo.addItem("1 Well (A1)")
                else:
                    well_list.append(f"A{cols}")
                    self._calibration_combo.addItems(
                        ["1 Well (A1)", f"2 Wells (A1,  A{cols})"]
                    )

            elif cols == 1:
                well_list.append(f"{well}{rows}")
                self._calibration_combo.addItems(
                    ["1 Well (A1)", f"2 Wells (A1, {well}{rows})"]
                )
            else:
                well_list.extend((f"A{cols}", f"{well}{1}", f"{well}{cols}"))
                self._calibration_combo.addItems(
                    [
                        "1 Well (A1)",
                        f"2 Wells (A1,  A{cols})",
                    ]
                )

            if from_combo:
                self._calibration_combo.setCurrentText(from_combo)

        n_tables = self._calibration_combo.currentText()[0]
        self._show_hide_tables(int(n_tables), well_list)

        if self._calibration_combo.currentText()[0] == "1":
            wells_to_calibrate = self._calibration_combo.currentText()[8:-1]
        else:
            wells_to_calibrate = self._calibration_combo.currentText()[9:-1]

        if self.plate.get("circular"):  # type: ignore
            text = (
                f"Calibrate Wells: {wells_to_calibrate}\n"
                "\n"
                "Add 3 points on the circonference of the round well "
                "and click on 'Calibrate Plate'."
            )
        else:
            text = (
                f"Calibrate Wells: {wells_to_calibrate}\n"
                "\n"
                "Add 2 points (opposite vertices) "
                "or 4 points (1 point per side) "
                "and click on 'Calibrate Plate'."
            )
        self.info_lbl.setText(text)

    def _set_calibrated(self, state: bool) -> None:
        if state:
            self.is_calibrated = True
            self.icon_lbl.setPixmap(
                icon(MDI6.check_bold, color=(0, 255, 0)).pixmap(QSize(20, 20))
            )
            self.cal_lbl.setText("Plate Calibrated!")
        else:
            self.is_calibrated = False
            self.A1_well = ()  # type: ignore
            self.plate_rotation_matrix = None  # type: ignore
            self.plate_angle_deg = 0.0
            self.icon_lbl.setPixmap(
                icon(MDI6.close_octagon_outline, color="magenta").pixmap(QSize(30, 30))
            )
            self.cal_lbl.setText("Plate non Calibrated!")

    def _get_circle_center_(
        self, a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]
    ) -> Tuple[float, float]:
        """Find the center of a round well given 3 edge points."""
        # eq circle (x - x1)^2 + (y - y1)^2 = r^2
        # for point a: (x - ax)^2 + (y - ay)^2 = r^2
        # for point b: = (x - bx)^2 + (y - by)^2 = r^2
        # for point c: = (x - cx)^2 + (y - cy)^2 = r^2

        x1, y1 = a
        x2, y2 = b
        x3, y3 = c

        x, y = symbols("x y")

        eq1 = Eq(
            (x - round(x1)) ** 2 + (y - round(y1)) ** 2,
            (x - round(x2)) ** 2 + (y - round(y2)) ** 2,
        )
        eq2 = Eq(
            (x - round(x1)) ** 2 + (y - round(y1)) ** 2,
            (x - round(x3)) ** 2 + (y - round(y3)) ** 2,
        )

        dict_center = solve((eq1, eq2), (x, y))

        try:
            xc = dict_center[x]
            yc = dict_center[y]
        except TypeError as e:
            self._set_calibrated(False)
            raise TypeError("Invalid Coordinates!") from e

        return float(xc), float(yc)

    @overload
    def _get_rect_center(
        self,
        a: Tuple[float, float],
        b: Tuple[float, float],
        c: Tuple[float, float],
        d: Tuple[float, float],
    ) -> Tuple:
        ...

    @overload
    def _get_rect_center(
        self, a: Tuple[float, float], b: Tuple[float, float]
    ) -> Tuple[float, float]:
        ...

    def _get_rect_center(self, *args) -> Tuple[float, float]:  # type: ignore
        """
        Find the center of a rectangle/square well.

        (given two opposite verices coordinates or 4 points on the edges).
        """
        # add block if wrong coords!!!
        x_list = [x[0] for x in [*args]]
        y_list = [y[1] for y in [*args]]
        x_max, x_min = (max(x_list), min(x_list))
        y_max, y_min = (max(y_list), min(y_list))

        if x_max == x_min or y_max == y_min:
            raise ValueError("Invalid Coordinates!")

        x_val = abs(x_min) if x_min < 0 else 0
        y_val = abs(y_min) if y_min < 0 else 0

        x1, y1 = (x_min + x_val, y_max + y_val)
        x2, y2 = (x_max + x_val, y_min + y_val)

        x_max_, x_min_ = (max(x1, x2), min(x1, x2))
        y_max_, y_min_ = (max(y1, y2), min(y1, y2))

        xc = ((x_max_ - x_min_) / 2) - x_val
        yc = ((y_max_ - y_min_) / 2) - y_val

        if x_min > 0:
            xc += x_min
        if y_min > 0:
            yc += y_min

        return xc, yc

    def _calibrate_plate(self) -> None:

        self._set_calibrated(False)

        if not self._mmc.getPixelSizeUm():
            raise ValueError("Pixel Size not defined! Set pixel size first.")

        if self._mmc.isSequenceRunning():
            self._mmc.stopSequenceAcquisition()

        if not self.plate:
            return

        self.table_1._handle_error(circular_well=self.plate.get("circular"))
        if not self.table_2.isHidden():
            self.table_2._handle_error(circular_well=self.plate.get("circular"))

        xc_w1, yc_w1 = self._get_well_center(self.table_1)
        xy_coords = [(xc_w1, yc_w1)]
        if not self.table_2.isHidden():
            xc_w2, yc_w2 = self._get_well_center(self.table_2)
            xy_coords.append((xc_w2, yc_w2))

        if len(xy_coords) > 1:
            self._calculate_plate_rotation_matrix(xy_coords)

        self._set_calibrated(True)

        if self.plate.get("id") == "_from calibration":
            pos = self._get_pos_from_table(self.table_1)
            self.PlateFromCalibration.emit(pos)

    def _calculate_plate_rotation_matrix(self, xy_coord_list: List[Tuple]) -> None:

        if len(xy_coord_list) == 2:
            x_1, y_1 = xy_coord_list[0]
            x_2, y_2 = xy_coord_list[1]

            m = (y_2 - y_1) / (x_2 - x_1)  # slope from y = mx + q
            plate_angle_rad = -np.arctan(m)
            self.plate_angle_deg = np.rad2deg(plate_angle_rad)
            self.plate_rotation_matrix = np.array(
                [
                    [np.cos(plate_angle_rad), -np.sin(plate_angle_rad)],
                    [np.sin(plate_angle_rad), np.cos(plate_angle_rad)],
                ]
            )

            logger.info(f"plate angle: {self.plate_angle_deg} deg.")
            logger.info(f"rotation matrix: \n{self.plate_rotation_matrix}.")

    def _get_pos_from_table(self, table: QTableWidget) -> Tuple[Tuple[float, float]]:
        pos = ()
        _range = table.tb.rowCount()
        for r in range(_range):
            x = float(table.tb.item(r, 1).text())
            y = float(table.tb.item(r, 2).text())
            pos += ((x, y),)  # type: ignore
        return pos  # type: ignore

    def _get_well_center(self, table: QTableWidget) -> Tuple[float, float]:

        pos = self._get_pos_from_table(table)

        if self.plate.get("circular"):  # type: ignore
            xc, yc = self._get_circle_center_(*pos)  # type: ignore
        else:
            xc, yc = self._get_rect_center(*pos)  # type: ignore

        if table == self.table_1:
            self.A1_well = ("A1", xc, yc)

        if self.plate.get("id") == "_from calibration":  # type: ignore
            self.PlateFromCalibration.emit(pos)

        return xc, yc


class CalibrationTable(QWidget):
    """Table for the calibration widget."""

    def __init__(self, *, mmcore: Optional[CMMCorePlus] = None) -> None:
        super().__init__()

        self._mmc = mmcore or CMMCorePlus.instance()

        self._well_name = ""

        self._create_wdg()

    def _create_wdg(self) -> None:
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 0, 0, 0)
        self.setLayout(layout)

        self.tb = QTableWidget()
        self.tb.setMinimumHeight(150)
        hdr = self.tb.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        self.tb.verticalHeader().setVisible(False)
        self.tb.setTabKeyNavigation(True)
        self.tb.setColumnCount(3)
        self.tb.setRowCount(0)
        self.tb.setHorizontalHeaderLabels(["Well", "X", "Y"])
        self.tb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tb, 0, 0, 3, 1)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        min_size = 100
        add_btn = QPushButton(text="Add")
        add_btn.clicked.connect(self._add_pos)
        add_btn.setMinimumWidth(min_size)
        add_btn.setSizePolicy(btn_sizepolicy)
        remove_btn = QPushButton(text="Remove")
        remove_btn.clicked.connect(self._remove_position_row)
        remove_btn.setMinimumWidth(min_size)
        remove_btn.setSizePolicy(btn_sizepolicy)
        clear_btn = QPushButton(text="Clear")
        clear_btn.clicked.connect(self._clear_table)
        clear_btn.setMinimumWidth(min_size)
        clear_btn.setSizePolicy(btn_sizepolicy)
        layout.addWidget(add_btn, 0, 1, 1, 1)
        layout.addWidget(remove_btn, 1, 1, 1, 2)
        layout.addWidget(clear_btn, 2, 1, 1, 2)

    def _add_pos(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("WXY"):
                if ax == "W":
                    item = QTableWidgetItem(f"{self._well_name}_pos{idx:03d}")
                else:
                    cur = getattr(self._mmc, f"get{ax}Position")()
                    item = QTableWidgetItem(str(cur))

                item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                self.tb.setItem(idx, c, item)

    def _add_position_row(self) -> int:
        idx = self.tb.rowCount()
        self.tb.insertRow(idx)
        return int(idx)

    def _remove_position_row(self) -> None:
        rows = {r.row() for r in self.tb.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.tb.removeRow(idx)

        self._rename_positions()

    def _rename_positions(self) -> None:
        pos_list = []
        name = ""
        for r in range(self.tb.rowCount()):
            curr_name = self.tb.item(r, 0).text()

            if r == 0:
                name = curr_name.split("_")[0]

            curr_pos = int(curr_name[-3:])
            pos_list.append(curr_pos)

        missing = [x for x in range(pos_list[0], pos_list[-1] + 1) if x not in pos_list]

        full = sorted(missing + pos_list)[: self.tb.rowCount()]

        for r in range(self.tb.rowCount()):
            new_name = f"{name}_pos{full[r]:03d}"
            item = QTableWidgetItem(new_name)
            item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
            self.tb.setItem(r, 0, item)

    def _clear_table(self) -> None:
        self.tb.clearContents()
        self.tb.setRowCount(0)

    def _rename_well_column(self, well_name: str) -> None:
        self._well_name = well_name
        well = QTableWidgetItem(well_name)
        self.tb.setHorizontalHeaderItem(0, well)

    def _handle_error(self, circular_well: bool) -> None:

        if circular_well:
            if self.tb.rowCount() < 3:
                raise ValueError(
                    f"Not enough points for {self._well_name}. "
                    "Add 3 points to the table."
                )
            elif self.tb.rowCount() > 3:
                raise ValueError("Add only 3 points to the table.")

        elif self.tb.rowCount() < 2 or self.tb.rowCount() == 3:
            raise ValueError(
                f"Not enough points for {self._well_name}. "
                "Add 2 or 4 points to the table."
            )
        elif self.tb.rowCount() > 4:
            raise ValueError("Add 2 or 4 points to the table.")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    win = PlateCalibration()
    win.show()
    sys.exit(app.exec_())
