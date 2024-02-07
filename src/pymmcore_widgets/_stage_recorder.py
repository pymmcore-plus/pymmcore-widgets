from typing import Optional, Tuple

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from superqt.fonticon import icon
from vispy import scene
from vispy.scene.visuals import Markers, Rectangle

BTN_SIZE = (60, 40)
W = "white"


class StageRecorder(QWidget):
    """A stage positions viewer widget."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
        show_fov: bool = True,
    ) -> None:
        super().__init__(parent)

        self._show_fov = show_fov

        self._mmc = mmcore or CMMCorePlus.instance()

        self._visited_positions: list[tuple[float, float]] = []
        self._fov_max: tuple[int, int] = (1, 1)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        layout.addWidget(self.canvas.native)

        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)

        btns = QWidget()
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)
        btns_layout.setContentsMargins(5, 5, 5, 5)
        btns.setLayout(btns_layout)
        # clear button
        self._clear_btn = QPushButton()
        self._clear_btn.setToolTip("Clear")
        self._clear_btn.clicked.connect(self._clear)
        self._clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_btn.setIcon(icon(MDI6.close_box_outline))
        self._clear_btn.setIconSize(QSize(25, 25))
        self._clear_btn.setFixedSize(*BTN_SIZE)
        # reset view button
        self._reset_view_btn = QPushButton()
        self._reset_view_btn.setToolTip("Reset View")
        self._reset_view_btn.clicked.connect(self._reset_view)
        self._reset_view_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._reset_view_btn.setIcon(icon(MDI6.home_outline))
        self._reset_view_btn.setIconSize(QSize(25, 25))
        self._reset_view_btn.setFixedSize(*BTN_SIZE)
        # add buttons to layout
        btns_layout.addStretch(1)
        btns_layout.addWidget(self._clear_btn)
        btns_layout.addWidget(self._reset_view_btn)

        layout.addWidget(btns)

        self._mmc.events.imageSnapped.connect(self._on_image_snapped)

    @property
    def show_fov(self) -> bool:
        return self._show_fov

    @show_fov.setter
    def show_fov(self, value: bool) -> None:
        self._show_fov = value

    def _on_image_snapped(self) -> None:
        # get current position (maybe find a different way to get the position)
        x, y = self._mmc.getXPosition(), self._mmc.getYPosition()

        # set the max fov depending on the image size
        self._set_max_fov()

        # return if the position is already visited
        if (x, y) in self._visited_positions:
            return

        self._visited_positions.append((x, y))
        img_width = self._mmc.getImageWidth() * self._mmc.getPixelSizeUm()
        img_height = self._mmc.getImageHeight() * self._mmc.getPixelSizeUm()
        self._draw_fov(x, y, img_width, img_height)
        self._reset_view()

    def _draw_fov(self, x: float, y: float, width: int, height: int) -> None:
        """Draw a the position on the canvas."""
        if self._show_fov:
            # draw the position as a fov around the (x, y) position coordinates
            fov = Rectangle(center=(x, y), width=width, height=height, border_color=W)
        else:
            # draw the (x, y) position as a point
            fov = Markers(pos=np.array([[x, y]]), edge_color=W, face_color=W)
        self.view.add(fov)

    def _get_edges_from_visited_positions(
        self,
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        x = [pos[0] for pos in self._visited_positions]
        y = [pos[1] for pos in self._visited_positions]

        # take in consideration the max fov
        x_min, x_max = min(x), max(x)
        y_min, y_max = min(y), max(y)
        return (
            (x_min - self._fov_max[0], x_max + self._fov_max[0]),
            (y_min - self._fov_max[1], y_max + self._fov_max[1]),
        )

    def _set_max_fov(self) -> None:
        """Set the max fov based on the image size.

        The max size is stored in self._fov_max so that if during the session the image
        size changes, the max fov will be updated and the view will be properly reset.
        """
        img_width = self._mmc.getImageWidth() * self._mmc.getPixelSizeUm()
        img_height = self._mmc.getImageHeight() * self._mmc.getPixelSizeUm()

        current_width_max, current_height_max = self._fov_max
        self._fov_max = (max(img_width, current_width_max), max(img_height, current_height_max))

    def _clear(self) -> None:
        # clear visited position list
        self._visited_positions.clear()

        # remove markers
        for child in reversed(self.view.scene.children):
            # if isinstance(child, (Markers, Rectangle)):
            if isinstance(child, (Rectangle)):
                child.parent = None

        self._reset_view()

    def _reset_view(self) -> None:
        if not self._visited_positions:
            self.view.camera.set_range()
            return
        (x_min, x_max), (y_min, y_max) = self._get_edges_from_visited_positions()
        self.view.camera.set_range(x=(x_min, x_max), y=(y_min, y_max))
