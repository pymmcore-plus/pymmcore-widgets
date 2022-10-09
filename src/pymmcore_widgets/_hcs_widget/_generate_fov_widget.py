import contextlib
import math
import random
import time
import warnings
from typing import List, Optional, Tuple

import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QPen
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from ._graphics_items import FOVPoints, WellArea

AlignCenter = Qt.AlignmentFlag.AlignCenter


class SelectFOV(QWidget):
    """Widget to select the FOVs of the sample plate."""

    def __init__(self, *, mmcore: Optional[CMMCorePlus] = None) -> None:
        super().__init__()

        self._mmc = mmcore or CMMCorePlus.instance()

        self._plate_size_x: float = None  # type: ignore
        self._plate_size_y: float = None  # type: ignore
        self._is_circular: bool = None  # type: ignore

        self._create_widget()

        self._mmc.events.pixelSizeChanged.connect(self._on_px_size_changed)

    def _create_widget(self) -> None:

        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.tab_wdg = QTabWidget()
        self.tab_wdg.setMinimumHeight(150)

        self.center_wdg = self._center_wdg_gui()
        self.random_wdg = self._random_wdg_gui()
        self.grid_wdg = self._grid_wdg_gui()

        self.tab_wdg.addTab(self.center_wdg, "Center")
        self.tab_wdg.addTab(self.random_wdg, "Random")
        self.tab_wdg.addTab(self.grid_wdg, "Grid")

        layout.addWidget(self.tab_wdg)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene, self)
        self.view.setStyleSheet("background:grey;")
        self._view_size = 200
        self.scene.setSceneRect(QRectF(0, 0, self._view_size, self._view_size))
        self.view.setFixedSize(self._view_size + 2, self._view_size + 2)

        layout.addWidget(self.view)

        self.tab_wdg.currentChanged.connect(self._on_tab_changed)

    def _create_label(
        self, layout: QLayout, widget: QWidget, label_text: str
    ) -> QLabel:

        layout.addWidget(widget)
        result = QLabel()
        result.setMinimumWidth(110)
        result.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        result.setText(label_text)
        return result

    def _random_wdg_gui(self) -> QWidget:

        random_wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        random_wdg.setLayout(layout)

        group_wdg = QWidget()
        group_wdg_layout = QVBoxLayout()
        group_wdg_layout.setSpacing(5)
        group_wdg_layout.setContentsMargins(10, 10, 10, 10)
        group_wdg.setLayout(group_wdg_layout)
        plate_area_label_x = self._create_label(layout, group_wdg, "Area x (mm):")

        self.plate_area_x = QDoubleSpinBox()
        self.plate_area_x.setAlignment(AlignCenter)
        self.plate_area_x.setMinimum(0.01)
        self.plate_area_x.setSingleStep(0.1)
        self.plate_area_x.valueChanged.connect(self._on_area_changed)
        _plate_area_x = self._make_QHBoxLayout_wdg_with_label(
            plate_area_label_x, self.plate_area_x
        )
        plate_area_label_y = self._create_label(
            group_wdg_layout, _plate_area_x, "Area y (mm):"
        )

        self.plate_area_y = QDoubleSpinBox()
        self.plate_area_y.setAlignment(AlignCenter)
        self.plate_area_y.setMinimum(0.01)
        self.plate_area_y.setSingleStep(0.1)
        self.plate_area_y.valueChanged.connect(self._on_area_changed)
        _plate_area_y = self._make_QHBoxLayout_wdg_with_label(
            plate_area_label_y, self.plate_area_y
        )
        number_of_FOV_label = self._create_label(
            group_wdg_layout, _plate_area_y, "FOVs:"
        )

        self.number_of_FOV = QSpinBox()
        self.number_of_FOV.setAlignment(AlignCenter)
        self.number_of_FOV.setMinimum(1)
        self.number_of_FOV.setMaximum(100)
        self.number_of_FOV.valueChanged.connect(self._on_number_of_FOV_changed)
        nFOV = self._make_QHBoxLayout_wdg_with_label(
            number_of_FOV_label, self.number_of_FOV
        )
        group_wdg_layout.addWidget(nFOV)

        self.random_button = QPushButton(text="Generate Random FOV(s)")
        self.random_button.clicked.connect(self._on_random_button_pressed)
        group_wdg_layout.addWidget(self.random_button)

        return random_wdg

    def _grid_wdg_gui(self) -> QWidget:

        grid_wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        grid_wdg.setLayout(layout)

        group_wdg = QWidget()
        group_wdg_layout = QVBoxLayout()
        group_wdg_layout.setSpacing(5)
        group_wdg_layout.setContentsMargins(10, 10, 10, 10)
        group_wdg.setLayout(group_wdg_layout)
        rows_lbl = self._create_label(layout, group_wdg, "Rows:")
        self.rows = QSpinBox()
        self.rows.setAlignment(AlignCenter)
        self.rows.setMinimum(1)
        self.rows.valueChanged.connect(self._on_grid_changed)
        _rows = self._make_QHBoxLayout_wdg_with_label(rows_lbl, self.rows)
        cols_lbl = self._create_label(group_wdg_layout, _rows, "Columns:")

        self.cols = QSpinBox()
        self.cols.setAlignment(AlignCenter)
        self.cols.setMinimum(1)
        self.cols.valueChanged.connect(self._on_grid_changed)
        _cols = self._make_QHBoxLayout_wdg_with_label(cols_lbl, self.cols)
        spacing_x_lbl = self._create_label(group_wdg_layout, _cols, "Spacing x (um):")

        self.spacing_x = QDoubleSpinBox()
        self.spacing_x.setAlignment(AlignCenter)
        self.spacing_x.setMinimum(-10000)
        self.spacing_x.setMaximum(100000)
        self.spacing_x.setSingleStep(100.0)
        self.spacing_x.setValue(0)
        self.spacing_x.valueChanged.connect(self._on_grid_changed)
        _spacing_x = self._make_QHBoxLayout_wdg_with_label(
            spacing_x_lbl, self.spacing_x
        )
        spacing_y_lbl = self._create_label(
            group_wdg_layout, _spacing_x, "Spacing y (um):"
        )

        self.spacing_y = QDoubleSpinBox()
        self.spacing_y.setAlignment(AlignCenter)
        self.spacing_y.setMinimum(-10000)
        self.spacing_y.setMaximum(100000)
        self.spacing_y.setSingleStep(100.0)
        self.spacing_y.setValue(0)
        self.spacing_y.valueChanged.connect(self._on_grid_changed)
        _spacing_y = self._make_QHBoxLayout_wdg_with_label(
            spacing_y_lbl, self.spacing_y
        )
        group_wdg_layout.addWidget(_spacing_y)

        return grid_wdg

    def _center_wdg_gui(self) -> QWidget:

        center_wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        center_wdg.setLayout(layout)

        group_wdg = QWidget()
        group_wdg_layout = QVBoxLayout()
        group_wdg_layout.setSpacing(5)
        group_wdg_layout.setContentsMargins(10, 10, 10, 10)
        group_wdg.setLayout(group_wdg_layout)
        plate_area_label_x = self._create_label(layout, group_wdg, "Area x (mm):")

        self.plate_area_x_c = QDoubleSpinBox()
        self.plate_area_x_c.setEnabled(False)
        self.plate_area_x_c.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.plate_area_x_c.setAlignment(AlignCenter)
        self.plate_area_x_c.setMinimum(1)
        _plate_area_x = self._make_QHBoxLayout_wdg_with_label(
            plate_area_label_x, self.plate_area_x_c
        )
        plate_area_label_y = self._create_label(
            group_wdg_layout, _plate_area_x, "Area y (mm):"
        )

        self.plate_area_y_c = QDoubleSpinBox()
        self.plate_area_y_c.setEnabled(False)
        self.plate_area_y_c.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.plate_area_y_c.setAlignment(AlignCenter)
        self.plate_area_y_c.setMinimum(1)
        _plate_area_y = self._make_QHBoxLayout_wdg_with_label(
            plate_area_label_y, self.plate_area_y_c
        )
        number_of_FOV_label = self._create_label(
            group_wdg_layout, _plate_area_y, "FOVs:"
        )

        self.number_of_FOV_c = QSpinBox()
        self.number_of_FOV_c.setEnabled(False)
        self.number_of_FOV_c.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.number_of_FOV_c.setAlignment(AlignCenter)
        self.number_of_FOV_c.setValue(1)
        nFOV = self._make_QHBoxLayout_wdg_with_label(
            number_of_FOV_label, self.number_of_FOV_c
        )
        group_wdg_layout.addWidget(nFOV)

        return center_wdg

    def _make_QHBoxLayout_wdg_with_label(self, label: QLabel, wdg: QWidget) -> QWidget:

        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(label)
        layout.addWidget(wdg)
        widget.setLayout(layout)

        return widget

    def _on_px_size_changed(self) -> None:
        with contextlib.suppress(AttributeError):
            for item in self.scene.items():
                if isinstance(item, (WellArea, FOVPoints)):
                    self.scene.removeItem(item)
            mode = self.tab_wdg.tabText(self.tab_wdg.currentIndex())
            if mode in ["Center", "Random"]:
                self._reset_center_random_scene(mode)
            else:  # Grid
                self._reset_grid_scene()

    def _reset_center_random_scene(self, mode: str) -> None:
        nFOV = self.number_of_FOV.value()
        area_x = self.plate_area_x.value()
        area_y = self.plate_area_y.value()
        self._update_FOV_center_random(nFOV, mode, area_x, area_y)

    def _reset_grid_scene(self) -> None:
        rows = self.rows.value()
        cols = self.cols.value()
        dx = self.spacing_x.value()
        dy = -(self.spacing_y.value())
        self._update_FOV_grid(rows, cols, dx, dy)

    def _on_tab_changed(self, tab_index: int) -> None:
        for item in self.scene.items():
            if isinstance(item, (WellArea, FOVPoints)):
                self.scene.removeItem(item)
        if tab_index != 2:  # Center or Random
            mode = "Center" if tab_index == 0 else "Random"
            self._reset_center_random_scene(mode)
        else:  # Grid
            self._reset_grid_scene()

    def _on_area_changed(self) -> None:
        for item in self.scene.items():
            if isinstance(item, (WellArea, FOVPoints)):
                self.scene.removeItem(item)
        self._reset_center_random_scene("Random")

    def _on_number_of_FOV_changed(self) -> None:
        for item in self.scene.items():
            if isinstance(item, FOVPoints):
                self.scene.removeItem(item)
        self._reset_center_random_scene("Random")

    def _on_grid_changed(self) -> None:
        for item in self.scene.items():
            if isinstance(item, FOVPoints):
                self.scene.removeItem(item)
        self._reset_grid_scene()

    def _load_plate_info(self, size_x: float, size_y: float, is_circular: bool) -> None:

        self.scene.clear()

        self._plate_size_x = round(size_x, 3)
        self._plate_size_y = round(size_y, 3)
        self._is_circular = is_circular

        if (
            self._plate_size_x == self._plate_size_y
            or self._plate_size_x < self._plate_size_y
        ):
            self._scene_size_x = 160
        else:
            self._scene_size_x = 180

        if (
            self._plate_size_y == self._plate_size_x
            or self._plate_size_y < self._plate_size_x
        ):
            self._scene_size_y = 160
        else:
            self._scene_size_y = 180

        self._scene_start_x = (self._view_size - self._scene_size_x) / 2
        self._scene_start_y = (self._view_size - self._scene_size_y) / 2

        pen = QPen(Qt.green)
        pen.setWidth(4)
        if self._is_circular:
            self.scene.addEllipse(
                self._scene_start_x,
                self._scene_start_y,
                self._scene_size_x,
                self._scene_size_y,
                pen,
            )
        else:
            self.scene.addRect(
                self._scene_start_x,
                self._scene_start_y,
                self._scene_size_x,
                self._scene_size_y,
                pen,
            )

        self._set_spinboxes_values(self.plate_area_x, self.plate_area_y)
        self._set_spinboxes_values(self.plate_area_x_c, self.plate_area_y_c)
        self.plate_area_y.setEnabled(not self._is_circular)
        self.plate_area_y.setButtonSymbols(
            QAbstractSpinBox.NoButtons
            if self._is_circular
            else QAbstractSpinBox.UpDownArrows
        )
        self.plate_area_x.setEnabled(True)

        mode = self.tab_wdg.tabText(self.tab_wdg.currentIndex())
        if mode in ["Center", "Random"]:
            self._reset_center_random_scene(mode)
        else:  # Grid
            self._reset_grid_scene()

    def _set_spinboxes_values(
        self, spin_x: QDoubleSpinBox, spin_y: QDoubleSpinBox
    ) -> None:
        with signals_blocked(spin_x):
            spin_x.setMaximum(self._plate_size_x)
            spin_x.setValue(self._plate_size_x)
        with signals_blocked(spin_y):
            spin_y.setMaximum(self._plate_size_y)
            spin_y.setValue(self._plate_size_y)

    def _on_random_button_pressed(self) -> None:

        for item in self.scene.items():
            if isinstance(item, FOVPoints):
                self.scene.removeItem(item)

        mode = self.tab_wdg.tabText(self.tab_wdg.currentIndex())
        self._reset_center_random_scene(mode)

    def _update_FOV_grid(self, rows: int, cols: int, dx: float, dy: float) -> None:

        if not self._mmc.getCameraDevice():
            return

        if not self._mmc.getPixelSizeUm():
            raise ValueError("Pixel Size not defined! Set pixel size first.")

        cr, cc = (self._view_size / 2, self._view_size / 2)

        _cam_x = self._mmc.getROI(self._mmc.getCameraDevice())[-2]
        _cam_y = self._mmc.getROI(self._mmc.getCameraDevice())[-1]
        _image_size_mm_x = (_cam_x * self._mmc.getPixelSizeUm()) / 1000
        _image_size_mm_y = (_cam_y * self._mmc.getPixelSizeUm()) / 1000

        # cam fov size in scene pixels
        self._x_size = (self._scene_size_x * _image_size_mm_x) / self._plate_size_x
        self._y_size = (self._scene_size_y * _image_size_mm_y) / self._plate_size_y

        scene_px_mm_x = self._plate_size_x / self._scene_size_x  # mm
        scene_px_mm_y = self._plate_size_y / self._scene_size_y  # mm
        dy = (dy / 1000) / scene_px_mm_y
        dx = (dx / 1000) / scene_px_mm_x

        if rows == 1 and cols == 1:
            x = cr
            y = cc
        else:
            x = cc - ((cols - 1) * (self._x_size / 2)) - ((dx / 2) * (cols - 1))
            y = cr + ((rows - 1) * (self._y_size / 2)) - ((dy / 2) * (rows - 1))

        move_x = self._x_size + dx
        move_y = self._y_size - dy

        points = self._create_grid_of_points(rows, cols, x, y, move_x, move_y)

        for p in points:
            self.scene.addItem(
                FOVPoints(
                    p[0],
                    p[1],
                    self._scene_size_x,
                    self._scene_size_y,
                    self._plate_size_x,
                    self._plate_size_y,
                    _image_size_mm_x,
                    _image_size_mm_y,
                    p[2],
                    p[3],
                )
            )

    def _create_grid_of_points(
        self, rows: int, cols: int, x: float, y: float, move_x: float, move_y: float
    ) -> List[Tuple[float, float, int, int]]:
        # for 'snake' acquisition
        points = []
        for r in range(rows):
            if r % 2:  # for odd rows
                col = cols - 1
                for c in range(cols):
                    if c == 0:
                        y -= move_y
                    points.append((x, y, r, c))
                    if col > 0:
                        col -= 1
                        x -= move_x
            else:  # for even rows
                for c in range(cols):
                    if r > 0 and c == 0:
                        y -= move_y
                    points.append((x, y, r, c))
                    if c < cols - 1:
                        x += move_x
        return points

    def _update_FOV_center_random(
        self, nFOV: int, mode: str, area_x: float, area_y: float
    ) -> None:
        if not self._mmc.getCameraDevice():
            return

        if not self._mmc.getPixelSizeUm():
            raise ValueError("Pixel Size not defined! Set pixel size first.")

        _cam_x = self._mmc.getROI(self._mmc.getCameraDevice())[-2]
        _cam_y = self._mmc.getROI(self._mmc.getCameraDevice())[-1]
        _image_size_mm_x = (_cam_x * self._mmc.getPixelSizeUm()) / 1000
        _image_size_mm_y = (_cam_y * self._mmc.getPixelSizeUm()) / 1000

        area_pen = QPen(Qt.magenta)
        area_pen.setWidth(4)

        if self._is_circular:
            self._update_scene_if_circular(
                nFOV, mode, area_x, _image_size_mm_x, _image_size_mm_y, area_pen
            )
        else:
            self._update_scene_if_rectangular(
                nFOV, mode, area_x, area_y, _image_size_mm_x, _image_size_mm_y, area_pen
            )

    def _update_scene_if_circular(
        self,
        nFOV: int,
        mode: str,
        area_x: float,
        _image_size_mm_x: float,
        _image_size_mm_y: float,
        area_pen: QPen,
    ) -> None:
        if mode == "Center":
            center_x, center_y = (self._view_size / 2, self._view_size / 2)
            self.scene.addItem(
                FOVPoints(
                    center_x,
                    center_y,
                    self._scene_size_x,
                    self._scene_size_y,
                    self._plate_size_x,
                    self._plate_size_y,
                    _image_size_mm_x,
                    _image_size_mm_y,
                )
            )

        elif mode == "Random":
            diameter = (self._scene_size_x * area_x) / self._plate_size_x
            center = (self._view_size - diameter) / 2

            self.scene.addItem(
                WellArea(True, center, center, diameter, diameter, area_pen)
            )

            min_dist_x = (self._scene_size_x * _image_size_mm_x) / area_x
            min_dist_y = (self._scene_size_y * _image_size_mm_y) / area_x

            points = self._random_points_in_circle(
                nFOV, diameter, center, min_dist_x, min_dist_y
            )
            for p in points:
                self.scene.addItem(
                    FOVPoints(
                        p[0],
                        p[1],
                        self._scene_size_x,
                        self._scene_size_y,
                        self._plate_size_x,
                        self._plate_size_y,
                        _image_size_mm_x,
                        _image_size_mm_y,
                    )
                )

    def _update_scene_if_rectangular(
        self,
        nFOV: int,
        mode: str,
        area_x: float,
        area_y: float,
        _image_size_mm_x: float,
        _image_size_mm_y: float,
        area_pen: QPen,
    ) -> None:

        if mode == "Center":
            center_x, center_y = (self._view_size / 2, self._view_size / 2)
            self.scene.addItem(
                FOVPoints(
                    center_x,
                    center_y,
                    self._scene_size_x,
                    self._scene_size_y,
                    self._plate_size_x,
                    self._plate_size_y,
                    _image_size_mm_x,
                    _image_size_mm_y,
                )
            )

        elif mode == "Random":
            size_x = (self._scene_size_x * area_x) / self._plate_size_x
            center_x = (self._view_size - size_x) / 2
            size_y = (self._scene_size_y * area_y) / self._plate_size_y
            center_y = (self._view_size - size_y) / 2

            self.scene.addItem(
                WellArea(False, center_x, center_y, size_x, size_y, area_pen)
            )

            points_area_x = (self._scene_size_x * area_x) / self._plate_size_x
            min_dist_x = (self._scene_size_x * _image_size_mm_x) / area_x
            points_area_y = (self._scene_size_y * area_y) / self._plate_size_y
            min_dist_y = (self._scene_size_y * _image_size_mm_y) / area_y

            points = self._random_points_in_square(
                nFOV,
                points_area_x,
                points_area_y,
                self._view_size,
                self._view_size,
                min_dist_x,
                min_dist_y,
            )
            for p in points:
                self.scene.addItem(
                    FOVPoints(
                        p[0],
                        p[1],
                        self._scene_size_x,
                        self._scene_size_y,
                        self._plate_size_x,
                        self._plate_size_y,
                        _image_size_mm_x,
                        _image_size_mm_y,
                    )
                )

    def _random_points_in_circle(
        self,
        nFOV: int,
        diameter: float,
        center: float,
        min_dist_x: float,
        min_dist_y: float,
    ) -> List[Tuple[float, float]]:

        radius = round(diameter / 2)
        _to_add = center + radius
        points: List[Tuple[float, float]] = []
        t = time.time()
        while len(points) < nFOV:
            # random angle
            alpha = 2 * math.pi * random.random()
            # random radius
            r = np.random.randint(0, radius)
            # calculating coordinates
            x = r * math.cos(alpha) + _to_add
            y = r * math.sin(alpha) + _to_add
            if self._dist((x, y), points, (min_dist_x, min_dist_y)):
                points.append((x, y))
            t1 = time.time()
            if t1 - t > 1:
                warnings.warn(
                    f"Area too small to generate {nFOV} fovs. "
                    f"Only {len(points)} were generated."
                )
                with signals_blocked(self.number_of_FOV):
                    self.number_of_FOV.setValue(len(points))
                return points
        return points

    def _random_points_in_square(
        self,
        nFOV: int,
        size_x: float,
        size_y: float,
        max_size_x: int,
        max_size_y: int,
        min_dist_x: float,
        min_dist_y: float,
    ) -> List[Tuple[float, float]]:

        x_left = (max_size_x - size_x) / 2  # left bound
        x_right = x_left + size_x  # right bound
        y_up = (max_size_y - size_y) / 2  # upper bound
        y_down = y_up + size_y  # lower bound

        points: List[Tuple[float, float]] = []

        t = time.time()
        while len(points) < nFOV:
            x = np.random.uniform(x_left, x_right)
            y = np.random.uniform(y_up, y_down)
            if self._dist((x, y), points, (min_dist_x, min_dist_y)):
                points.append((x, y))
            t1 = time.time()
            if t1 - t > 0.5:
                warnings.warn(
                    f"Area too small to generate {nFOV} fovs. "
                    f"Only {len(points)} were generated."
                )
                with signals_blocked(self.number_of_FOV):
                    self.number_of_FOV.setValue(len(points))
                return points
        return points

    def _dist(
        self,
        new_point: Tuple[float, float],
        points: List[Tuple[float, float]],
        min_distance: Tuple[float, float],
    ) -> bool:

        x_new, y_new = new_point[0], new_point[1]
        min_distance_x, min_distance_y = min_distance[0], min_distance[1]
        for point in points:
            x, y = point[0], point[1]
            x_max, x_min = max(x, x_new), min(x, x_new)
            y_max, y_min = max(y, y_new), min(y, y_new)
            if x_max - x_min < min_distance_x and y_max - y_min < min_distance_y:
                return False
        return True
