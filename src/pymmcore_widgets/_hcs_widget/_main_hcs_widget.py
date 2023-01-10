from __future__ import annotations

import math
import random
import string
import warnings
from pathlib import Path

import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked
from useq import MDASequence

from pymmcore_widgets._hcs_widget._calibration_widget import PlateCalibration
from pymmcore_widgets._hcs_widget._generate_fov_widget import SelectFOV
from pymmcore_widgets._hcs_widget._graphics_items import FOVPoints, Well
from pymmcore_widgets._hcs_widget._plate_graphics_scene_widget import HCSGraphicsScene
from pymmcore_widgets._hcs_widget._update_plate_dialog import UpdatePlateDialog
from pymmcore_widgets._hcs_widget._well_plate_database import PLATE_DB, WellPlate
from pymmcore_widgets._mda._mda_widget import MDAWidget
from pymmcore_widgets._util import PLATE_FROM_CALIBRATION

AlignCenter = Qt.AlignmentFlag.AlignCenter

ALPHABET = string.ascii_uppercase
CALIBRATED_PLATE: WellPlate | None = None


class HCSWidget(QWidget):
    """HCS widget.

    Parameters
    ----------
    parent : Optional[QWidget]
        Optional parent widget, by default None
    include_run_button: bool
        By default, False. If true, a "run" button is added to the widget.
        The acquisition defined by the `useq.MDASequence` built through the
        widget is executed when clicked.
    mmcore: Optional[CMMCorePlus]
        Optional `CMMCorePlus` micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new) `CMMCorePlus.instance()`.

    The `HCSWidget` provides a GUI to construct a `useq.MDASequence` object.
    It can be used to automate the acquisition of multi-well plate
    or custom defined areas.
    If the `include_run_button` parameter is set to `True`, a "run" button is added
    to the GUI and, when clicked, the generated `useq.MDASequence` is passed to the
    `CMMCorePlus.run_mda` method and the acquisition is executed.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        # scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(AlignCenter)
        layout.addWidget(scroll)

        # tabwidget
        self.tabwidget = QTabWidget()
        self.tabwidget.setTabPosition(QTabWidget.West)

        self._select_plate_tab = self._create_plate_and_fov_tab()

        self._calibration = self._create_calibration_tab()

        self._mda = HCSMDA(parent=self)
        self._mda.add_positions_button.clicked.connect(self._generate_pos_list)
        self._mda.position_groupbox.load_positions_button.clicked.connect(
            self._load_positions
        )
        self._mda.position_groupbox.save_positions_button.clicked.connect(
            self._save_positions
        )

        self.tabwidget.addTab(self._select_plate_tab, "  Plate and FOVs Selection  ")
        self.tabwidget.addTab(self._calibration, "  Plate Calibration  ")
        self.tabwidget.addTab(self._mda, "  MDA  ")
        scroll.setWidget(self.tabwidget)

        # connect
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg)
        self._mmc.events.roiSet.connect(self._on_roi_set)

        self.wp_combo.currentTextChanged.connect(self._on_combo_changed)
        self.custom_plate.clicked.connect(self._show_update_plate_dialog)
        self.clear_button.clicked.connect(self.scene._clear_selection)
        self.calibration.PlateFromCalibration.connect(self._on_plate_from_calibration)
        self.calibration._test_button.clicked.connect(self._test_calibration)

        self._refresh_wp_combo()

    def _create_plate_and_fov_tab(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(20)
        wdg_layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(wdg_layout)

        self.scene = HCSGraphicsScene(parent=self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setStyleSheet("background:grey;")
        self._width = 500
        self._height = 300
        self.view.setMinimumSize(self._width, self._height)

        # well plate selector combo and clear selection QPushButton
        upper_wdg = QWidget()
        upper_wdg_layout = QHBoxLayout()
        upper_wdg_layout.setSpacing(5)
        upper_wdg_layout.setContentsMargins(0, 0, 0, 5)
        wp_combo_wdg = self._create_wp_combo_selector()
        btns = self._create_btns()
        upper_wdg_layout.addWidget(wp_combo_wdg)
        upper_wdg_layout.addWidget(btns)
        upper_wdg.setLayout(upper_wdg_layout)

        self.FOV_selector = SelectFOV(parent=self)

        # add widgets
        view_group = QGroupBox()
        view_group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        view_gp_layout = QVBoxLayout()
        view_gp_layout.setSpacing(0)
        view_gp_layout.setContentsMargins(10, 10, 10, 10)
        view_group.setLayout(view_gp_layout)
        view_gp_layout.addWidget(upper_wdg)
        view_gp_layout.addWidget(self.view)
        wdg_layout.addWidget(view_group)

        FOV_group = QGroupBox()
        FOV_group.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        FOV_gp_layout = QVBoxLayout()
        FOV_gp_layout.setSpacing(0)
        FOV_gp_layout.setContentsMargins(10, 10, 10, 10)
        FOV_group.setLayout(FOV_gp_layout)
        FOV_gp_layout.addWidget(self.FOV_selector)
        wdg_layout.addWidget(FOV_group)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        wdg_layout.addItem(verticalSpacer)

        return wdg

    def _create_wp_combo_selector(self) -> QWidget:

        combo_wdg = QWidget()
        wp_combo_layout = QHBoxLayout()
        wp_combo_layout.setContentsMargins(0, 0, 0, 0)
        wp_combo_layout.setSpacing(5)

        combo_label = QLabel()
        combo_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        combo_label.setText("Plate:")

        self.wp_combo = QComboBox()

        wp_combo_layout.addWidget(combo_label)
        wp_combo_layout.addWidget(self.wp_combo)
        combo_wdg.setLayout(wp_combo_layout)

        return combo_wdg

    def _create_btns(self) -> QWidget:
        btns_wdg = QWidget()
        btns_layout = QHBoxLayout()
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.setSpacing(5)
        btns_wdg.setLayout(btns_layout)

        self.custom_plate = QPushButton(text="Custom Plate")
        self.clear_button = QPushButton(text="Clear Selection")
        btns_layout.addWidget(self.custom_plate)
        btns_layout.addWidget(self.clear_button)

        return btns_wdg

    def _create_calibration_tab(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(20)
        wdg_layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(wdg_layout)

        cal_group = QGroupBox()
        cal_group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        cal_group_layout = QVBoxLayout()
        cal_group_layout.setSpacing(0)
        cal_group_layout.setContentsMargins(10, 20, 10, 10)
        cal_group.setLayout(cal_group_layout)
        self.calibration = PlateCalibration(parent=self)
        cal_group_layout.addWidget(self.calibration)
        wdg_layout.addWidget(cal_group)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        wdg_layout.addItem(verticalSpacer)

        return wdg

    def _set_enabled(self, enabled: bool) -> None:
        self._select_plate_tab.setEnabled(enabled)
        self._calibration.setEnabled(enabled)
        self._mda.setEnabled(enabled)

    def _on_sys_cfg(self) -> None:
        self._set_enabled(True)
        self._on_combo_changed(self.wp_combo.currentText())

    def _refresh_wp_combo(self) -> None:
        self.wp_combo.clear()
        self.wp_combo.addItems(list(PLATE_DB))

    def _on_combo_changed(self, value: str) -> None:
        self.scene.clear()
        self._draw_well_plate(value)
        self.calibration._update_gui(value)

        self.calibration._well_letter_combo.clear()
        letters = [ALPHABET[letter] for letter in range(PLATE_DB[value].rows)]
        self.calibration._well_letter_combo.addItems(letters)

        self.calibration._well_number_combo.clear()
        numbers = [str(c) for c in range(1, PLATE_DB[value].cols + 1)]
        self.calibration._well_number_combo.addItems(numbers)

    def _test_calibration(self) -> None:

        if not self.calibration.plate:
            return

        well_letter = self.calibration._well_letter_combo.currentText()
        well_number = self.calibration._well_number_combo.currentText()
        center = self._get_well_and_fovs_position_list(
            self._get_wells_stage_coords(
                [
                    (
                        f"{well_letter}{well_number}",
                        self.calibration._well_letter_combo.currentIndex(),
                        self.calibration._well_number_combo.currentIndex(),
                    )
                ]
            )
        )
        _, xc, yc = center[0]
        if self.calibration.plate.circular:
            self._move_to_circle_edge(xc, yc, self.calibration.plate.well_size_x / 2)
        else:
            self._move_to_rectangle_edge(
                xc,
                yc,
                self.calibration.plate.well_size_x,
                self.calibration.plate.well_size_y,
            )

    def _move_to_circle_edge(self, xc: float, yc: float, radius: float) -> None:
        # random angle
        alpha = 2 * math.pi * random.random()
        move_x = radius * math.cos(alpha) + xc
        move_y = radius * math.sin(alpha) + yc
        self._mmc.setXYPosition(move_x, move_y)

    def _move_to_rectangle_edge(
        self, xc: float, yc: float, well_size_x: float, well_size_y: float
    ) -> None:
        x_top_left = xc - (well_size_x / 2)
        y_top_left = yc + (well_size_y / 2)

        x_bottom_right = xc + (well_size_x / 2)
        y_bottom_right = yc - (well_size_y / 2)

        x = np.random.uniform(x_top_left, x_bottom_right)
        y = np.random.uniform(y_top_left, y_bottom_right)

        if x <= xc:
            if y >= yc:
                move_x, move_y = (
                    (x_top_left, y)  # quad 1 - LEFT
                    if abs(x_top_left - x) < abs(y_top_left - y)
                    else (x, y_top_left)  # quad 1 - TOP
                )
            elif abs(x_top_left - x) < abs(y_bottom_right - y):
                move_x, move_y = (x_top_left, y)  # quad 3 - LEFT
            else:
                move_x, move_y = (x, y_bottom_right)  # quad 3 - BOTTOM
        elif y >= yc:
            move_x, move_y = (
                (x_bottom_right, y)  # quad 2 - RIGHT
                if abs(x_bottom_right - x) < abs(y_top_left - y)
                else (x, y_top_left)  # quad 2 - TOP
            )
        elif abs(x_bottom_right - x) < abs(y_bottom_right - y):
            move_x, move_y = (x_bottom_right, y)  # quad 4 - RIGHT
        else:
            move_x, move_y = (x, y_bottom_right)  # quad 4 - BOTTOM

        self._mmc.setXYPosition(move_x, move_y)

    def _on_roi_set(self) -> None:
        self._on_combo_changed(self.wp_combo.currentText())

    def _on_plate_from_calibration(self, coords: tuple) -> None:
        global CALIBRATED_PLATE

        x_list, y_list = zip(*coords)
        CALIBRATED_PLATE = WellPlate(
            circular=False,
            id=PLATE_FROM_CALIBRATION,
            cols=1,
            rows=1,
            well_size_x=(max(x_list) - min(x_list)) / 1000,
            well_size_y=(max(y_list) - min(y_list)) / 1000,
            well_spacing_x=0,
            well_spacing_y=0,
        )

        self.scene.clear()
        self._draw_well_plate(CALIBRATED_PLATE)

    def _draw_well_plate(self, well_plate: str | WellPlate) -> None:
        self.wp = PLATE_DB[well_plate] if isinstance(well_plate, str) else well_plate

        max_w = self._width - 10
        max_h = self._height - 10
        start_y = 0.0

        if self.wp.rows == 1 and self.wp.cols > 1:
            size_x = max_w / self.wp.cols
            size_y = size_x
            start_y = (max_h / 2) - (size_y / 2)

        elif self.wp.cols == 1 and self.wp.rows > 1:
            size_y = max_h / self.wp.rows
            size_x = size_y

        else:
            size_y = max_h / self.wp.rows
            size_x = (
                size_y
                if (self.wp.circular or self.wp.well_size_x == self.wp.well_size_y)
                else (max_w / self.wp.cols)
            )
        text_size = size_y / 3  # 2.3

        width = size_x * self.wp.cols

        if width != self.scene.width() and self.scene.width() > 0:
            start_x = (self.scene.width() - width) / 2
            start_x = max(start_x, 0)
        else:
            start_x = 0

        self._create_well_plate(
            self.wp.rows,
            self.wp.cols,
            start_x,
            start_y,
            size_x,
            size_y,
            text_size,
            self.wp.circular,
        )

        # select the plate area if is not a multi well
        items = self.scene.items()
        if len(items) == 1:
            item = items[0]
            item.setSelected(True)
            item._setBrush(QBrush(Qt.magenta))

        self.FOV_selector._load_plate_info(
            self.wp.well_size_x, self.wp.well_size_y, self.wp.circular
        )

    def _create_well_plate(
        self,
        rows: int,
        cols: int,
        start_x: float,
        start_y: float,
        size_x: float,
        size_y: float,
        text_size: float,
        circular: bool,
    ) -> None:
        x = start_x
        y = start_y
        for row in range(rows):
            for col in range(cols):
                self.scene.addItem(
                    Well(x, y, size_x, size_y, row, col, text_size, circular)
                )
                x += size_x
            y += size_y
            x = start_x

    def _show_update_plate_dialog(self) -> None:
        self.plate = UpdatePlateDialog(parent=self)
        self.plate.plate_updated.connect(self._update_wp_combo)
        self.plate.show()
        self._clear_values()

    def _clear_values(self) -> None:
        self.plate._circular_checkbox.setChecked(False)
        self.plate._id.setText("")
        self.plate._cols.setValue(0)
        self.plate._rows.setValue(0)
        self.plate._well_size_x.setValue(0.0)
        self.plate._well_size_y.setValue(0.0)
        self.plate._well_spacing_x.setValue(0.0)
        self.plate._well_spacing_y.setValue(0.0)

    def _update_wp_combo(self, new_plate: WellPlate | None) -> None:
        with signals_blocked(self.wp_combo):
            self.wp_combo.clear()
            self.wp_combo.addItems(list(PLATE_DB))

        if new_plate is not None:
            self.wp_combo.setCurrentText(new_plate.id)
            self._on_combo_changed(new_plate.id)
        else:
            self.wp_combo.setCurrentIndex(0)
            self._on_combo_changed(self.wp_combo.itemText(0))

    def _generate_pos_list(self) -> None:

        if not self.calibration.is_calibrated:
            warnings.warn("Plate not calibrated! Calibrate it first.")
            return

        if not self._mmc.getPixelSizeUm():
            warnings.warn("Pixel Size not defined! Set pixel size first.")
            return

        well_list = self.scene._get_plate_positions()

        if not well_list:
            warnings.warn("No Well selected! Select at least one well first.")
            return

        self._mda.position_groupbox._clear_positions()

        ordered_wells_list = self._get_wells_stage_coords(well_list)

        ordered_wells_and_fovs_list = self._get_well_and_fovs_position_list(
            ordered_wells_list
        )

        for f in ordered_wells_and_fovs_list:
            well_name, stage_coord_x, stage_coord_y = f
            zpos = self._mmc.getPosition() if self._mmc.getFocusDevice() else None
            self._mda.position_groupbox.create_row(
                well_name, stage_coord_x, stage_coord_y, zpos
            )

    def _get_wells_stage_coords(
        self, well_list: list[tuple[str, int, int]]
    ) -> list[tuple[str, float, float]]:

        if self.wp is None or self.calibration.A1_well is None:
            return []

        calculated_spacing_x = self.calibration._calculated_well_spacing_x
        calculated_spacing_y = self.calibration._calculated_well_spacing_x

        if calculated_spacing_x is None or calculated_spacing_y is None:
            return []

        # center stage coords of calibrated well a1
        a1_x = self.calibration.A1_well[1]
        a1_y = self.calibration.A1_well[2]
        center = np.array([[a1_x], [a1_y]])
        r_matrix = self.calibration.plate_rotation_matrix

        # distance between wells from plate database (mm)
        ordered_well_list = []
        original_pos_list = []
        for pos in well_list:
            well, row, col = pos
            # find center stage coords for all the selected wells
            if well == "A1":
                x = a1_x
                y = a1_y
                original_pos_list.append((x, y))

            else:
                x = a1_x + (calculated_spacing_x * col)
                y = a1_y - (calculated_spacing_y * row)
                original_pos_list.append((x, y))

                if r_matrix is not None:

                    coords = [[x], [y]]

                    transformed = np.linalg.inv(r_matrix).dot(coords - center) + center

                    x_rotated, y_rotated = transformed
                    x = x_rotated[0]
                    y = y_rotated[0]

            ordered_well_list.append((well, x, y))

        return ordered_well_list

    def _get_well_and_fovs_position_list(
        self, ordered_wells_list: list[tuple[str, float, float]]
    ) -> list[tuple[str, float, float]]:
        if self.wp is None:
            return []

        calculated_size_x = self.calibration._calculated_well_size_x
        calculated_size_y = self.calibration._calculated_well_size_y

        if calculated_size_x is None or calculated_size_y is None:
            return []

        fovs = [
            item._getPositionsInfo()
            for item in self.FOV_selector.scene.items()
            if isinstance(item, FOVPoints)
        ]
        fovs.reverse()

        # center coord in px (of QGraphicsView))
        cx = 100
        cy = 100

        pos_list = []

        r_matrix = self.calibration.plate_rotation_matrix

        for pos in ordered_wells_list:
            well_name, center_stage_x, center_stage_y = pos

            for idx, fov in enumerate(fovs):
                # center fov scene x, y coord fx and fov scene width and height
                (
                    center_fov_scene_x,
                    center_fov_scene_y,
                    w_fov_scene,
                    h_fov_scene,
                ) = fov

                # find 1 px value in um depending on well dimension
                px_val_x = calculated_size_x / w_fov_scene  # µm
                px_val_y = calculated_size_y / h_fov_scene  # µm

                # shift point coords in scene when center is (0, 0)
                new_fx = center_fov_scene_x - cx
                new_fy = center_fov_scene_y - cy

                # find stage coords of fov point
                stage_coord_x = center_stage_x + (new_fx * px_val_x)
                stage_coord_y = center_stage_y + (new_fy * px_val_y)

                if r_matrix is not None:

                    center = np.array([[center_stage_x], [center_stage_y]])

                    coords = [[stage_coord_x], [stage_coord_y]]

                    transformed = np.linalg.inv(r_matrix).dot(coords - center) + center

                    x_rotated, y_rotated = transformed
                    stage_coord_x = x_rotated[0]
                    stage_coord_y = y_rotated[0]

                pos_list.append(
                    (f"{well_name}_pos{idx:03d}", stage_coord_x, stage_coord_y)
                )

        return pos_list

    def _save_positions(self) -> None:
        if not self._mda.position_groupbox._table.rowCount():
            return

        (dir_file, _) = QFileDialog.getSaveFileName(
            self, "Saving directory and filename.", "", "json(*.json)"
        )
        if not dir_file:
            return

        import json

        save_file = self._mda.position_groupbox.value()
        center_coords = {
            "name": "A1_center_coords",
            "x": self.calibration.A1_stage_coords_center[0],
            "y": self.calibration.A1_stage_coords_center[1],
        }
        save_file.insert(0, center_coords)  # type: ignore

        with open(str(dir_file), "w") as file:
            json.dump(save_file, file)

    def _load_positions(self) -> None:
        if not self.calibration.is_calibrated:
            warnings.warn("Plate not calibrated! Calibrate it first.")
            return

        (filename, _) = QFileDialog.getOpenFileName(
            self, "Select a position list file", "", "json(*.json)"
        )
        if filename:
            import json

            with open(filename) as file:
                self._add_loaded_positions_and_translate(json.load(file))

    def _add_loaded_positions_and_translate(self, pos_list: list) -> None:

        new_xc, new_yc = self.calibration.A1_stage_coords_center

        self._mda.position_groupbox._clear_positions()

        delta_x, delta_y = (0.0, 0.0)
        for pos in pos_list:

            name = pos.get("name")

            if name == "A1_center_coords":
                old_xc = pos.get("x")
                old_yc = pos.get("y")
                delta_x = old_xc - new_xc
                delta_y = old_yc - new_yc
                continue

            new_x = pos.get("x") - delta_x
            new_y = pos.get("y") - delta_y
            zpos = pos.get("z")

            self._mda.position_groupbox.create_row(name, new_x, new_y, zpos)

    def get_state(self) -> MDASequence:
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        return self._mda.get_state()

    def set_state(self, state: dict | MDASequence | str | Path) -> None:
        """Set current state of MDA widget.

        Parameters
        ----------
        state : dict | MDASequence | str | Path
            MDASequence state in the form of a dict, MDASequence object, or a str or
            Path pointing to a sequence.yaml file
        """
        return self._mda.set_state(state)


class HCSMDA(MDAWidget):
    """Subclass of MDAWidget to modify PositionTable."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, include_run_button=True, mmcore=mmcore)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.channel_groupbox.setMaximumHeight(200)

        # modufy position table widget
        self._central_widget.layout().removeWidget(self.position_groupbox)
        self._central_widget.layout().insertWidget(0, self.position_groupbox)
        self.position_groupbox.setMinimumHeight(300)
        self.position_groupbox.setChecked(True)
        self.position_groupbox.toggled.connect(self._set_checked)
        self.position_groupbox.grid_button.hide()

        # replace add button
        pos_tb_wdg = self.position_groupbox.layout().itemAt(0).widget()
        btns_wdg = pos_tb_wdg.layout().itemAt(1).widget()
        self.position_groupbox.add_button.hide()
        self.add_positions_button = QPushButton(text="Add")
        btns_wdg.layout().insertWidget(0, self.add_positions_button)

        # disconnect save and load buttons
        self.position_groupbox.save_positions_button.clicked.disconnect()
        self.position_groupbox.load_positions_button.clicked.disconnect()

    def _set_checked(self) -> None:
        """Keep the QGroupBox always checked."""
        self.position_groupbox.setChecked(True)

    def _enable_run_btn(self) -> None:
        self.buttons_wdg.run_button.setEnabled(
            self.channel_groupbox._table.rowCount() > 0
            and self.position_groupbox._table.rowCount() > 0
        )


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    CMMCorePlus.instance().loadSystemConfiguration()
    app = QApplication(sys.argv)
    win = HCSWidget()

    win.show()
    sys.exit(app.exec_())
