from typing import cast

import numpy as np
import useq
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimerEvent, Signal
from qtpy.QtWidgets import (
    QAction,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Rectangle

from ._stage_viewer import StageViewer

gray = "#666"
RESET = "Reset View"
CLEAR = "Clear View"
SNAP = "Snap on Double Click"
POLL_STAGE = "Poll Stage Position"
FLIP_X = "Flip Images Horizontally"
FLIP_Y = "Flip Images Vertically"
MIN_XY_DIFF = 5

SS_TOOLBUTTON = """
    QToolButton {
        min-width: 25px;
        min-height: 25px;
        max-width: 25px;
        max-height: 25px;
    }
    QToolButton:checked {
        background-color: rgba(51, 170, 51, 255);
        border: 2px solid rgba(102, 102, 102, 255);
        border-radius: 5px;
    }
    QToolButton:!checked {
        border: 2px solid rgba(102, 102, 102, 255);
        border-radius: 5px;
    }
    QToolButton:checked:hover {
        background-color: rgba(51, 170, 51, 180);
    }
    QToolButton:!checked:hover {
        background-color: rgba(102, 102, 102, 100);
    }
"""


class RotationControl(QWidget):
    """A widget to set the rotation of the images."""

    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._rotation: int = 0

        self._cw_90 = QAction(
            icon(MDI6.rotate_right, color=gray), "Rotate 90° CW", self
        )
        self._ccw_90 = QAction(
            icon(MDI6.rotate_left, color=gray), "Rotate 90° CCW", self
        )
        self._lbl_value = QLabel("Rotation: 0°")

        self._cw_90.triggered.connect(lambda: self._update_rotation(90))
        self._ccw_90.triggered.connect(lambda: self._update_rotation(-90))

        toolbar = QToolBar()
        toolbar.setStyleSheet(SS_TOOLBUTTON)
        toolbar.setMovable(False)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addAction(self._cw_90)
        toolbar.addAction(self._ccw_90)
        toolbar.addWidget(self._lbl_value)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(toolbar)

    def _update_rotation(self, value: int) -> None:
        self._rotation += value
        self._lbl_value.setText(f"Rotation: {self._rotation}°")
        self.valueChanged.emit(self._rotation)

    def value(self) -> int:
        return self._rotation


class StageExplorer(QWidget):
    """A stage positions explorer widget.

    This widget provides a visual representation of the stage positions. The user can
    interact with the stage positions by panning and zooming the view. A `scaleChanged`
    signal is emitted when the scale changes. The user can also move the stage to a
    specific position (and, optionally, snap an image) by double-clicking on the view.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    mmc : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].

    Properties
    ----------
    image_store : dict[tuple[float, float], np.ndarray]
        Return the image_store dictionary object where the keys are the stage positions
        and values are the images added to the scene.
    snap_on_double_click : bool
        A boolean property that controls whether to snap an image when the user
        double-clicks on the view. By default, False.
    flip_x : bool
        A boolean property that controls whether to flip images horizontally. By
        default, False.
    flip_y : bool
        A boolean property that controls whether to flip images vertically. By default,
        False.
    poll_stage_position : bool
        A boolean property that controls whether to poll the stage position.
        If True, the widget will poll the stage position and display the current X and Y
        coordinates in the status bar and with a 'cross_lines' marker. If False, the
        widget will stop polling the stage position. By default, False.
    """

    scaleChanged = Signal(int)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._stage_viewer = StageViewer(self)

        # timer for polling stage position
        self._timer_id: int | None = None

        # properties
        self._snap_on_double_click: bool = False
        self._flip_horizontal: bool = False
        self._flip_vertical: bool = False
        self._poll_stage_position: bool = False
        self._rotation: int = 0

        # marker for stage position
        self._stage_pos_marker: Rectangle | None = None

        # to store stage xy position. used in timerEvent
        self._xy: tuple[float | None, float | None] = (None, None)

        # toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet(SS_TOOLBUTTON)
        toolbar.setMovable(False)
        toolbar.setContentsMargins(0, 0, 10, 0)

        # actions
        self._clear_view_act: QAction
        self._reset_view_act: QAction
        self._snap_on_double_click_act: QAction
        self._poll_stage_position_act: QAction
        self._flip_images_horizontally_act: QAction
        self._flip_images_vertically_act: QAction

        ACTION_MAP = {
            # action text: (icon, color, checkable, callback)
            CLEAR: (MDI6.close, gray, False, self.clear_scene),
            RESET: (MDI6.fullscreen, gray, False, self.reset_view),
            SNAP: (MDI6.camera_outline, gray, True, self._on_setting_checked),
            POLL_STAGE: (MDI6.map_marker, gray, True, self._on_poll_stage),
            "separator": (None, None, None, None),
            FLIP_X: (MDI6.flip_horizontal, gray, True, self._on_setting_checked),
            FLIP_Y: (MDI6.flip_vertical, gray, True, self._on_setting_checked),
        }

        # create actions
        for a_text, (a_icon, color, check, callback) in ACTION_MAP.items():
            if a_text == "separator":
                toolbar.addSeparator()
                continue
            action = QAction(icon(a_icon, color=color), a_text, self, checkable=check)
            action.triggered.connect(callback)
            setattr(self, f"_{a_text.lower().replace(' ', '_')}_act", action)
            toolbar.addAction(action)

        # set initial state of actions
        self._snap_on_double_click_act.setChecked(self._snap_on_double_click)
        self._poll_stage_position_act.setChecked(self._poll_stage_position)
        self._flip_images_horizontally_act.setChecked(self._flip_horizontal)
        self._flip_images_vertically_act.setChecked(self._flip_vertical)

        # add rotation control to the toolbar
        self._rotation_control = RotationControl()
        self._rotation_control.valueChanged.connect(self._on_rotation_changed)
        toolbar.addSeparator()
        toolbar.addWidget(self._rotation_control)
        toolbar.addSeparator()

        # add stage pos label to the toolbar
        self._stage_pos_label = QLabel()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.addWidget(spacer)
        toolbar.addWidget(self._stage_pos_label)

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(toolbar, 0)
        main_layout.addWidget(self._stage_viewer, 1)

        # connect vispy events
        self._stage_viewer.canvas.events.mouse_double_click.connect(
            self._move_to_clicked_position
        )
        self._stage_viewer.scaleChanged.connect(self.scaleChanged)

        # connections core events
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.pixelSizeChanged.connect(self._on_pixel_size_changed)
        self._mmc.events.roiSet.connect(self._on_roi_set)
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)

        self._on_sys_config_loaded()

    # -----------------------------PUBLIC METHODS-------------------------------------

    @property
    def image_store(self) -> dict[float, dict[tuple[float, float], np.ndarray]]:
        """Return the image store."""
        return self._stage_viewer.image_store

    @property
    def snap_on_double_click(self) -> bool:
        """Return the snap on double click property."""
        return self._snap_on_double_click

    @snap_on_double_click.setter
    def snap_on_double_click(self, value: bool) -> None:
        """Set the snap on double click property."""
        self._snap_on_double_click = value
        self._snap_on_double_click_act.setChecked(value)

    @property
    def poll_stage_position(self) -> bool:
        """Return the poll stage position property."""
        return self._poll_stage_position

    @poll_stage_position.setter
    def poll_stage_position(self, value: bool) -> None:
        """Set the poll stage position property."""
        self._poll_stage_position = value
        self._poll_stage_position_act.setChecked(value)
        self._on_poll_stage(value)

    @property
    def flip_horizontal(self) -> bool:
        """Return the flip x property."""
        return self._flip_horizontal

    @flip_horizontal.setter
    def flip_horizontal(self, value: bool) -> None:
        """Set the flip x property."""
        self._flip_horizontal = value
        self._flip_images_horizontally_act.setChecked(value)

    @property
    def flip_vertical(self) -> bool:
        """Return the flip y property."""
        return self._flip_vertical

    @flip_vertical.setter
    def flip_vertical(self, value: bool) -> None:
        """Set the flip y property."""
        self._flip_vertical = value
        self._flip_images_vertically_act.setChecked(value)

    def add_image(
        self,
        img: np.ndarray,
        x: float,
        y: float,
    ) -> None:
        """Add an image to the scene.

        The image is also added to the `image_store` which is a dictionary that uses the
        (x, y) positions as key and the images as value.

        Parameters
        ----------
        img : np.ndarray
            The image to add to the scene.
        x : float
            The x position of the image.
        y : float
            The y position of the image.
        """
        if self.flip_horizontal:
            img = np.flip(img, axis=1)
        if self.flip_vertical:
            img = np.flip(img, axis=0)
        # add rotation if it is != 0
        if (rotation := self._rotation_control.value()) != 0:
            img = np.rot90(img, rotation // 90)
        self._stage_viewer.add_image(img, x, y)

    def reset_view(self) -> None:
        """Recenter the view to the center of all images."""
        # NOTE: Not using the `reset_view` method from `StageViewer` directly because we
        # also need to consider the stage position marker.

        min_x, max_x, min_y, max_y = self._stage_viewer._get_full_boundaries()

        # consider the stage position marker if present
        mk_min_x, mk_min_y, mk_max_x, mk_max_y = self._get_stage_marker_position()
        if all(val is not None for val in (mk_min_x, mk_max_x, mk_min_y, mk_max_y)):
            min_x = min(min_x if min_x is not None else mk_min_x, mk_min_x)  # type: ignore
            max_x = max(max_x if max_x is not None else mk_max_x, mk_max_x)  # type: ignore
            min_y = min(min_y if min_y is not None else mk_min_y, mk_min_y)  # type: ignore
            max_y = max(max_y if max_y is not None else mk_max_y, mk_max_y)  # type: ignore

        if any(val is None for val in (min_x, max_x, min_y, max_y)):
            return

        self._stage_viewer.view.camera.set_range(x=(min_x, max_x), y=(min_y, max_y))

    def clear_scene(self) -> None:
        """Clear the scene."""
        self._stage_viewer.clear_scene()
        self.reset_view()

    # -----------------------------PRIVATE METHODS------------------------------------

    def _on_rotation_changed(self, value: int) -> None:
        """Update the rotation property."""
        self._rotation = value
        # reset the stage position marker
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.parent = None
            self._stage_pos_marker = None

    def _on_sys_config_loaded(self) -> None:
        """Set the pixel size when the system configuration is loaded."""
        self.clear_scene()
        self._stage_viewer.pixel_size = self._mmc.getPixelSizeUm()

    def _on_pixel_size_changed(self, value: float) -> None:
        """Clear the scene when the pixel size changes."""
        self._stage_viewer.pixel_size = value
        # delete stage position marker
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.parent = None
            self._stage_pos_marker = None

    def _on_roi_set(self) -> None:
        """Clear the scene when the ROI is set.

        If polling the stage position, the stage position marker will redraw.
        """
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.parent = None
            self._stage_pos_marker = None

    def _on_image_snapped(self) -> None:
        """Add the snapped image to the scene."""
        if self._mmc.mda.is_running():
            return
        # get the snapped image
        img = self._mmc.getImage()
        # get the current stage position
        x, y = self._mmc.getXYPosition()
        self._add_image_and_update_widget(img, x, y)

    def _on_frame_ready(self, image: np.ndarray, event: useq.MDAEvent) -> None:
        """Add the image to the scene when frameReady event is emitted."""
        # TODO: better handle c and z (e.g. multi-channels?, max projection?)
        x = event.x_pos if event.x_pos is not None else self._mmc.getXPosition()
        y = event.y_pos if event.y_pos is not None else self._mmc.getYPosition()
        self._add_image_and_update_widget(image, x, y)

    def _add_image_and_update_widget(
        self, image: np.ndarray, x: float, y: float
    ) -> None:
        """Add the image to the scene and update position label and view."""
        self.add_image(image, x, y)
        # update the stage position label if the stage position is not being polled
        if not self._poll_stage_position:
            self._stage_pos_label.setText(f"X: {x:.2f} µm  Y: {y:.2f} µm")
        # reset the view if the image is not within the view
        if not self._is_visual_within_view(x, y):
            self.reset_view()

    def _move_to_clicked_position(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice():
            return
        x, y, _, _ = self._stage_viewer.view.camera.transform.imap(event.pos)
        self._mmc.setXYPosition(x, y)
        # update the stage position label
        self._stage_pos_label.setText(f"X: {x:.2f} µm  Y: {y:.2f} µm")
        if self._snap_on_double_click:
            # wait for the stage to be in position before snapping an image
            self._mmc.waitForDevice(self._mmc.getXYStageDevice())
            self._mmc.snapImage()

    def _on_setting_checked(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        action_map = {
            self._snap_on_double_click_act: "snap_on_double_click",
            self._flip_images_horizontally_act: "flip_horizontal",
            self._flip_images_vertically_act: "flip_vertical",
        }
        sender = cast(QAction, self.sender())

        if value := action_map.get(sender):
            setattr(self, value, checked)

    def _on_poll_stage(self, checked: bool) -> None:
        """Set the poll stage position property based on the state of the action."""
        self._poll_stage_position = checked
        if checked:
            self._timer_id = self.startTimer(50)
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
            # delete markers
            if self._stage_pos_marker is not None:
                self._stage_pos_marker.parent = None
                self._stage_pos_marker = None

    def timerEvent(self, event: QTimerEvent) -> None:
        """Poll the stage position."""
        if not self._mmc.getXYStageDevice():
            return

        x, y = self._mmc.getXYPosition()

        # update the stage position label
        self._stage_pos_label.setText(f"X: {x:.2f} µm  Y: {y:.2f} µm")

        # add stage marker if not yet present
        if self._stage_pos_marker is None:
            w, h = self._mmc.getImageWidth(), self._mmc.getImageHeight()
            # invert width and height if the image is rotated (-) 90, 270, 450, etc.
            if self._rotation % 180 != 0:
                w, h = h, w
            self._stage_pos_marker = Rectangle(
                parent=self._stage_viewer.view.scene,
                center=(x, y),
                width=w * self._stage_viewer.pixel_size,
                height=h * self._stage_viewer.pixel_size,
                border_width=4,
                border_color="#3A3",
                color=None,
            )
            self._stage_pos_marker.set_gl_state(depth_test=False)
            self.reset_view()

        # update stage marker position
        self._stage_pos_marker.center = (x, y)

        # Compare the old and new xy positions; if the percentage difference exceeds 5%,
        # it means the stage position has significantly changed, so reset the view.
        # This is useful because we don't want to trigger reset_view when the user
        # changes the zoom level or pans the view or if the stage jittered a bit.
        # If acquiring, reset is handled by the _on_frame_ready method.
        if not self._mmc.mda.is_running() and all(val is not None for val in self._xy):
            old_x, old_y = self._xy
            if old_x is not None and old_y is not None:
                # 1e-6 is used to avoid division by zero
                diff_x = abs(x - old_x) / max(abs(old_x), 1e-6) * 100
                diff_y = abs(y - old_y) / max(abs(old_y), 1e-6) * 100
                if not self._is_visual_within_view(x, y) and (
                    diff_x > MIN_XY_DIFF or diff_y > MIN_XY_DIFF
                ):
                    self.reset_view()

        # Update _xy position with new values
        self._xy = (x, y)

    def _get_stage_marker_position(
        self,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Return the stage marker position.

        Returns
        -------
        tuple[float | None, float | None, float | None, float | None]
            The min x, min y, max x, and max y coordinates of the stage position marker.
            If the stage marker is not present, all values are None.
        """
        if self._stage_pos_marker is None:
            return None, None, None, None
        x, y = self._stage_pos_marker.center
        w, h = self._stage_pos_marker.width, self._stage_pos_marker.height
        min_x, min_y = x - w / 2, y - h / 2
        max_x, max_y = x + w / 2, y + h / 2
        return min_x, min_y, max_x, max_y

    def _is_visual_within_view(self, x: float, y: float) -> bool:
        """Return True if the visual is within the view, otherwise False."""
        view_rect = self._stage_viewer.view.camera.rect
        half_width = self._mmc.getImageWidth() / 2 * self._stage_viewer.pixel_size
        half_height = self._mmc.getImageHeight() / 2 * self._stage_viewer.pixel_size
        vertices = [
            (x - half_width, y - half_height),
            (x + half_width, y - half_height),
            (x - half_width, y + half_height),
            (x + half_width, y + half_height),
        ]
        return all(view_rect.contains(*vertex) for vertex in vertices)
