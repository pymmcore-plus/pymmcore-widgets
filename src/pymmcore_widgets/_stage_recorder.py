from typing import Any, Optional

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, QTimer
from qtpy.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from superqt.fonticon import icon
from useq import MDAEvent
from vispy import scene
from vispy.color import Color
from vispy.scene.visuals import Rectangle

_DEFAULT_WAIT = 100
BTN_SIZE = (60, 40)
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
        self._fov_max: tuple[float, float] = (1, 1)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        layout.addWidget(self.canvas.native)

        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)

        self.streaming_timer = QTimer(parent=self)
        self.streaming_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.streaming_timer.setInterval(int(self._mmc.getExposure()) or _DEFAULT_WAIT)
        self.streaming_timer.timeout.connect(self._on_streaming_timeout)

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
        self._clear_btn.clicked.connect(self._clear)
        # reset view button
        self._reset_view_btn = QPushButton()
        self._reset_view_btn.setToolTip("Reset View")
        self._reset_view_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._reset_view_btn.setIcon(icon(MDI6.home_outline))
        self._reset_view_btn.setIconSize(QSize(25, 25))
        self._reset_view_btn.setFixedSize(*BTN_SIZE)
        self._reset_view_btn.clicked.connect(self._reset_view)
        # stop stage button
        self._stop_stage_btn = QPushButton()
        self._stop_stage_btn.setToolTip("Stop Stage")
        self._stop_stage_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._stop_stage_btn.setIcon(icon(MDI6.stop))
        self._stop_stage_btn.setIconSize(QSize(25, 25))
        self._stop_stage_btn.setFixedSize(*BTN_SIZE)
        self._stop_stage_btn.clicked.connect(
            lambda: self._mmc.stop(self._mmc.getXYStageDevice())
        )
        # auto reset view checkbox
        self._auto_reset_checkbox = QCheckBox("Auto Reset View")
        self._auto_reset_checkbox.setChecked(True)
        self._auto_reset_checkbox.stateChanged.connect(self._on_reset_view_toggle)
        # autosnap checkbox
        self._autosnap_checkbox = QCheckBox("Auto Snap on double click")
        self._autosnap_checkbox.setChecked(False)
        # add buttons to layout
        btns_layout.addWidget(self._auto_reset_checkbox)
        btns_layout.addWidget(self._autosnap_checkbox)
        btns_layout.addStretch(1)
        btns_layout.addWidget(self._stop_stage_btn)
        btns_layout.addWidget(self._clear_btn)
        btns_layout.addWidget(self._reset_view_btn)

        layout.addWidget(btns)

        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)

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

        self._mmc.setXYPosition(x, y)

        if self._autosnap_checkbox.isChecked() and not self._mmc.isSequenceRunning():
            self._mmc.snapImage()

    def _on_reset_view_toggle(self, state: bool) -> None:
        if state:
            self._reset_view()

    def _on_streaming_start(self) -> None:
        self.streaming_timer.start()

    def _on_streaming_stop(self) -> None:
        self.streaming_timer.stop()

    def _on_exposure_changed(self, device: str, value: str) -> None:
        self.streaming_timer.setInterval(int(value))

    def _on_streaming_timeout(self) -> None:
        """Update the preview rectangle position."""
        # get current position
        x, y = self._mmc.getXPosition(), self._mmc.getYPosition()
        # delete the previous preview rectangle
        self._delete_scene_items(G)
        # draw the fov around the position
        self._draw_fov(x, y, G)
        if self._auto_reset_checkbox.isChecked():
            self._reset_view()

    def _on_frame_ready(self, img: np.ndarray, event: MDAEvent) -> None:
        """Update the scene with the position from an MDA acquisition."""
        x, y = event.x_pos, event.y_pos
        if x is not None and y is not None:
            self._update_scene(x, y)

    def _on_image_snapped(self) -> None:
        """Update the scene with the current position."""
        # get current position (maybe find a different way to get the position)
        x, y = self._mmc.getXPosition(), self._mmc.getYPosition()
        self._update_scene(x, y)

    def _update_scene(self, x: float, y: float) -> None:
        # set the max fov depending on the image size
        self._set_max_fov()

        # return if the position is already visited
        if (x, y) in self._visited_positions:
            return

        # add the position to the visited positions list
        self._visited_positions.append((x, y))

        # draw the fov around the position
        self._draw_fov(x, y, W)

        # reset the view if the auto reset checkbox is checked
        if self._auto_reset_checkbox.isChecked():
            self._reset_view()

    def _draw_fov(self, x: float, y: float, color: Color) -> None:
        """Draw a the position on the canvas."""
        # draw the position as a fov around the (x, y) position coordinates
        width = self._mmc.getImageWidth() * self._mmc.getPixelSizeUm()
        height = self._mmc.getImageHeight() * self._mmc.getPixelSizeUm()
        fov = Rectangle(center=(x, y), width=width, height=height, border_color=color)
        self.view.add(fov)

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

    def _set_max_fov(self) -> None:
        """Set the max fov based on the image size.

        The max size is stored in self._fov_max so that if during the session the image
        size changes, the max fov will be updated and the view will be properly reset.
        """
        img_width = self._mmc.getImageWidth() * self._mmc.getPixelSizeUm()
        img_height = self._mmc.getImageHeight() * self._mmc.getPixelSizeUm()

        current_width_max, current_height_max = self._fov_max
        self._fov_max = (
            max(img_width, current_width_max),
            max(img_height, current_height_max),
        )

    def _delete_scene_items(self, color: Color | None = None) -> None:
        """Delete all items of a given class from the scene.

        If color is specified, only the items with the given color will be deleted.
        """
        for child in reversed(self.view.scene.children):
            if isinstance(child, Rectangle) and (
                color is None or child.border_color == color
            ):
                child.parent = None

    def _clear(self) -> None:
        """Clear the visited positions and the scene."""
        # clear visited position list
        self._visited_positions.clear()
        # clear scene
        self._delete_scene_items()
        # reset view
        self._reset_view()

    def _reset_view(self) -> None:
        """Set the camera range to fit all the visited positions."""
        preview = self._get_preview_rect()
        if not self._visited_positions and not preview:
            self.view.camera.set_range()
            return

        # if only the marker is present, set the range to the marker position
        if not self._visited_positions and preview is not None:
            # get preview center position
            (x, y) = preview.center
            self.view.camera.set_range(
                x=(x - (preview.width / 2), x + (preview.width / 2)),
                y=(y - (preview.height / 2), y + (preview.height / 2)),
            )
            return

        # get the edges from all the visited positions
        (x_min, x_max), (y_min, y_max) = self._get_edges_from_visited_points()

        # if there is a preview rectangle, also consider its positio to set the range
        if preview is not None:
            # get marker position
            x, y = preview.center
            # compare the marker position with the edges
            x_min = min(x_min, x - (preview.width / 2))
            x_max = max(x_max, x + (preview.width / 2))
            y_min = min(y_min, y - (preview.height / 2))
            y_max = max(y_max, y + (preview.height / 2))

        self.view.camera.set_range(x=(x_min, x_max), y=(y_min, y_max))

    def _get_preview_rect(self) -> Rectangle | None:  # sourcery skip: use-next
        """Get the preview rectangle from the scene using its border color."""
        for child in self.view.scene.children:
            if isinstance(child, Rectangle) and child.border_color == G:
                return child
        return None
