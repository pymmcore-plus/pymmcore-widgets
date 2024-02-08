from typing import Any, Optional

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from skimage.transform import resize
from superqt.fonticon import icon
from useq import MDAEvent
from vispy import scene
from vispy.color import Color
from vispy.scene.visuals import Image
from vispy.visuals.transforms import STTransform

_DEFAULT_WAIT = 100
BTN_SIZE = (60, 40)
SCALE_FACTOR = 2
W = Color("white")
G = Color("green")


class StageRecorder(QWidget):
    """A stage positions viewer widget."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._visited_positions: list[tuple[float, float]] = []
        self._fov_max: tuple[float, float] = (0, 0)

        # comboboxes
        combos = QWidget()
        combos_layout = QHBoxLayout()
        combos_layout.setSpacing(10)
        combos_layout.setContentsMargins(5, 5, 5, 5)
        combos.setLayout(combos_layout)
        # flip horizontal checkbox
        self._flip_horizontal_checkbox = QCheckBox("Flip Horizontal")
        self._flip_horizontal_checkbox.setToolTip("Flip the image horizontally.")
        self._flip_horizontal_checkbox.setChecked(False)
        # flip vertical checkbox
        self._flip_vertical_checkbox = QCheckBox("Flip Vertical")
        self._flip_vertical_checkbox.setToolTip("Flip the image vertically.")
        self._flip_vertical_checkbox.setChecked(False)
        # auto reset view checkbox
        self._auto_reset_checkbox = QCheckBox("Auto Reset View")
        self._auto_reset_checkbox.setChecked(True)
        self._auto_reset_checkbox.stateChanged.connect(self._on_reset_view_toggle)
        # autosnap checkbox
        self._autosnap_checkbox = QCheckBox("Auto Snap on double click")
        self._autosnap_checkbox.setChecked(False)
        # add combos to layout
        combos_layout.addStretch(1)
        combos_layout.addWidget(self._flip_horizontal_checkbox)
        combos_layout.addWidget(self._flip_vertical_checkbox)
        combos_layout.addWidget(self._auto_reset_checkbox)
        combos_layout.addWidget(self._autosnap_checkbox)

        # canvas and view
        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)

        # buttons
        btns = QWidget()
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)
        btns_layout.setContentsMargins(5, 5, 5, 5)
        btns.setLayout(btns_layout)
        # clear button
        self._clear_btn = QPushButton()
        self._clear_btn.setToolTip("Clear")
        self._clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_btn.setIcon(icon(MDI6.close_box_outline))
        self._clear_btn.setIconSize(QSize(25, 25))
        self._clear_btn.setFixedSize(*BTN_SIZE)
        self._clear_btn.clicked.connect(self.clear)
        # reset view button
        self._reset_view_btn = QPushButton()
        self._reset_view_btn.setToolTip("Reset View")
        self._reset_view_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._reset_view_btn.setIcon(icon(MDI6.home_outline))
        self._reset_view_btn.setIconSize(QSize(25, 25))
        self._reset_view_btn.setFixedSize(*BTN_SIZE)
        self._reset_view_btn.clicked.connect(self.reset_view)
        # stop stage button
        self._stop_stage_btn = QPushButton()
        self._stop_stage_btn.setToolTip("Stop Stage")
        self._stop_stage_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._stop_stage_btn.setIcon(icon(MDI6.stop_circle_outline))
        self._stop_stage_btn.setIconSize(QSize(25, 25))
        self._stop_stage_btn.setFixedSize(*BTN_SIZE)
        self._stop_stage_btn.clicked.connect(
            lambda: self._mmc.stop(self._mmc.getXYStageDevice())
        )
        # add buttons to layout
        btns_layout.addWidget(self._stop_stage_btn)
        btns_layout.addStretch(1)
        btns_layout.addWidget(self._clear_btn)
        btns_layout.addWidget(self._reset_view_btn)

        # add to main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(main_layout)
        main_layout.addWidget(combos)
        main_layout.addWidget(self.canvas.native)
        main_layout.addWidget(btns)

        # this is to make the widget square
        # self.setMinimumHeight(self.minimumSizeHint().width())

        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)

        self.canvas.events.mouse_double_click.connect(self._on_mouse_double_click)

    def _on_mouse_double_click(self, event: Any) -> None:
        """Move the stage to the mouse position.

        If the autosnap checkbox is checked, also snap an image.
        """
        if self._mmc.mda.is_running():
            return

        # Get mouse position in camera coordinates
        x, y, _, _ = self.view.camera.transform.imap(event.pos)

        self._mmc.setXYPosition(x * SCALE_FACTOR, y * SCALE_FACTOR)

        if self._autosnap_checkbox.isChecked() and not self._mmc.isSequenceRunning():
            self._mmc.snapImage()

    def _on_reset_view_toggle(self, state: bool) -> None:
        if state:
            self.reset_view()

    def _set_max_fov(self) -> None:
        """Set the max fov based on the image size.

        The max size is stored in self._fov_max so that if during the session the image
        size changes, the max fov will be updated and the view will be properly reset.
        """
        img_width, img_height = self._get_image_size()

        current_width_max, current_height_max = self._fov_max
        self._fov_max = (
            max(img_width, current_width_max),
            max(img_height, current_height_max),
        )

    def _on_image_snapped(self) -> None:
        """Update the scene with the current position."""
        # if the mda is running, we will use the frameReady event to update the scene
        if self._mmc.mda.is_running():
            return

        # get snapped image
        image = self._mmc.getImage()
        # get current position
        x, y = self._mmc.getXPosition(), self._mmc.getYPosition()
        # update the scene with the image
        self._update_scene_with_image(image, x / SCALE_FACTOR, y / SCALE_FACTOR)

    def _on_frame_ready(self, image: np.ndarray, event: MDAEvent) -> None:
        x, y = event.x_pos, event.y_pos
        if x is not None and y is not None:
            self._update_scene_with_image(image, x / SCALE_FACTOR, y / SCALE_FACTOR)

    def _get_edges_from_visited_points(
        self,
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Get the edges of the visited positions."""
        x = [pos[0] for pos in self._visited_positions]
        y = [pos[1] for pos in self._visited_positions]
        x_min, x_max = (min(x), max(x))
        y_min, y_max = (min(y), max(y))
        # consider the fov size
        return (
            (x_min - self._fov_max[0], x_max + self._fov_max[0]),
            (y_min - self._fov_max[1], y_max + self._fov_max[1]),
        )

    def _delete_scene_images(self) -> None:
        """Delete all images from the scene."""
        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

    def clear(self) -> None:
        """Clear the scene and the visited positions."""
        # clear visited position list
        self._visited_positions.clear()
        # clear scene
        self._delete_scene_images()
        # reset view
        self.reset_view()

    def reset_view(self) -> None:
        """Set the camera range to fit all the visited positions."""
        if not self._visited_positions:
            self.view.camera.set_range()
            return

        # get the edges from all the visited positions
        (x_min, x_max), (y_min, y_max) = self._get_edges_from_visited_points()

        self.view.camera.set_range(x=(x_min, x_max), y=(y_min, y_max))

    def _get_image_size(self) -> tuple[float, float]:
        """Get the image size in pixel from the camera."""
        img_width = self._mmc.getImageWidth() * self._mmc.getPixelSizeUm()
        img_height = self._mmc.getImageHeight() * self._mmc.getPixelSizeUm()
        return img_width / SCALE_FACTOR, img_height / SCALE_FACTOR

    def _update_scene_with_image(self, image: np.ndarray, x: float, y: float) -> None:
        # return if the position is already visited
        if (x, y) in self._visited_positions:
            return

        # add the position to the visited positions list
        self._visited_positions.append((x, y))

        # set the max fov depending on the image size
        self._set_max_fov()

        # add the image to the scene
        self._add_image(image, x, y)

    def _add_image(self, image: np.ndarray, x: float, y: float) -> None:
        """Add an image to the scene."""
        width, height = self._get_image_size()

        # scale
        scaled = resize(image, (height, width))
        # flip horizontally
        if self._flip_horizontal_checkbox.isChecked():
            scaled = np.fliplr(scaled)
        # flip vertically
        if self._flip_vertical_checkbox.isChecked():
            scaled = np.flipud(scaled)

        scaled_8bit = (scaled / scaled.max()) * 255
        scaled_8bit = np.uint8(scaled_8bit)

        clim = (scaled_8bit.min(), scaled_8bit.max())

        frame = Image(scaled_8bit, cmap="grays", parent=self.view.scene, clim=clim)

        # set the position of the image so that the center of the image is at the given
        # (x, y) position
        x -= width / 2
        y -= height / 2
        frame.transform = STTransform(translate=(x, y))

        if self._auto_reset_checkbox.isChecked():
            self.reset_view()
