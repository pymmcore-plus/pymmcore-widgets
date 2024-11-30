import warnings
from typing import cast

import numpy as np
import useq
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimerEvent, Signal
from qtpy.QtWidgets import (
    QAction,
    QLabel,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Markers

from ._stage_viewer import StageViewer

gray = "#666"
RESET = "Reset View"
AUTO_RESET = "Auto Reset View"
CLEAR = "Clear View"
SNAP = "Snap on Double Click"
FLIP_X = "Flip Images Horizontally"
FLIP_Y = "Flip Images Vertically"
POLL_STAGE = "Poll Stage Position"

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
    auto_reset_view : bool
        A boolean property that controls whether to automatically reset the view when an
        image is added to the scene. By default, True.
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

    def __init__(self, parent: QWidget | None = None, mmc: CMMCorePlus | None = None):
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._mmc = mmc or CMMCorePlus.instance()

        self._stage_viewer = StageViewer()

        # timer for polling stage position
        self._timer_id: int | None = None

        # properties
        self._auto_reset_view: bool = True
        self._snap_on_double_click: bool = False
        self._flip_horizontal: bool = False
        self._flip_vertical: bool = False
        self._poll_stage_position: bool = False

        # marker for stage position
        self._stage_pos_marker: Markers | None = None

        # toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet(SS_TOOLBUTTON)
        toolbar.setMovable(False)
        toolbar.setContentsMargins(0, 0, 10, 0)

        # actions
        self._clear_view_act: QAction
        self._reset_view_act: QAction
        self._auto_reset_view_act: QAction
        self._snap_on_double_click_act: QAction
        self._flip_images_horizontally_act: QAction
        self._flip_images_vertically_act: QAction
        self._poll_stage_position_act: QAction

        ACTION_MAP = {
            # action text: (icon, color, checkable, callback)
            CLEAR: (MDI6.close, gray, False, self._stage_viewer.clear_scene),
            RESET: (MDI6.checkbox_blank_outline, gray, False, self.reset_view),
            AUTO_RESET: (MDI6.caps_lock, gray, True, self._on_reset_view),
            SNAP: (MDI6.camera_outline, gray, True, self._on_setting_checked),
            FLIP_X: (MDI6.flip_horizontal, gray, True, self._on_setting_checked),
            FLIP_Y: (MDI6.flip_vertical, gray, True, self._on_setting_checked),
            POLL_STAGE: (MDI6.map_marker, gray, True, self._on_poll_stage),
        }

        # create actions
        for a_text, (a_icon, color, check, callback) in ACTION_MAP.items():
            action = QAction(icon(a_icon, color=color), a_text, self, checkable=check)
            action.triggered.connect(callback)
            setattr(self, f"_{a_text.lower().replace(' ', '_')}_act", action)
            toolbar.addAction(action)

        # set initial state of actions
        self._auto_reset_view_act.setChecked(self._auto_reset_view)
        self._snap_on_double_click_act.setChecked(self._snap_on_double_click)
        self._flip_images_horizontally_act.setChecked(self._flip_horizontal)
        self._flip_images_vertically_act.setChecked(self._flip_vertical)
        self._poll_stage_position_act.setChecked(self._poll_stage_position)

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
        self._mmc.events.pixelSizeChanged.connect(self._on_pixel_size_changed)
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)

    # -----------------------------PUBLIC METHODS-------------------------------------

    @property
    def image_store(self) -> dict[tuple[float, float], np.ndarray]:
        """Return the image store."""
        return self._stage_viewer.image_store

    @property
    def auto_reset_view(self) -> bool:
        """Return the auto reset view property."""
        return self._auto_reset_view

    @auto_reset_view.setter
    def auto_reset_view(self, value: bool) -> None:
        """Set the auto reset view property."""
        self._auto_reset_view = value
        self._auto_reset_view_act.setChecked(value)
        if value:
            self.reset_view()

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

    def add_image(
        self,
        img: np.ndarray,
        x: float,
        y: float,
        flip_x: bool = False,
        flip_y: bool = False,
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
        flip_x : bool
            Flip the image horizontally, by default False.
        flip_y : bool
            Flip the image vertically, by default False.
        """
        if flip_x:
            img = np.flip(img, axis=1)
        if flip_y:
            img = np.flip(img, axis=0)
        self._stage_viewer.add_image(img, x, y)
        if self._auto_reset_view:
            self.reset_view()

    def reset_view(self) -> None:
        """Recenter the view to the center of all images."""
        # NOTE: Not using the `reset_view` method from `StageViewer` directly because we
        # also need to consider the stage position marker.

        min_x, max_x, min_y, max_y = self._stage_viewer._get_boundaries()

        # consider the stage position marker if present
        marker_x, marker_y = self._get_stage_marker_position()
        if marker_x is not None and marker_y is not None:
            min_x = min(min_x if min_x is not None else marker_x, marker_x)
            max_x = max(max_x if max_x is not None else marker_x, marker_x)
            min_y = min(min_y if min_y is not None else marker_y, marker_y)
            max_y = max(max_y if max_y is not None else marker_y, marker_y)

        if any(val is None for val in (min_x, max_x, min_y, max_y)):
            return

        self._stage_viewer.view.camera.set_range(x=(min_x, max_x), y=(min_y, max_y))

    # -----------------------------PRIVATE METHODS------------------------------------

    def _on_reset_view(self, checked: bool) -> None:
        """Set the auto reset view property based on the state of the action."""
        self._auto_reset_view = checked
        if checked:
            self.reset_view()

    def _on_poll_stage(self, checked: bool) -> None:
        """Set the poll stage position property based on the state of the action."""
        if checked:
            self._timer_id = self.startTimer(50)
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
            self._stage_pos_label.setText("")
            # delete markers
            if self._stage_pos_marker is not None:
                self._stage_pos_marker.parent = None
                self._stage_pos_marker = None

    def timerEvent(self, event: QTimerEvent) -> None:
        """Poll the stage position."""
        if not self._mmc.getXYStageDevice():
            return
        x, y = self._mmc.getXYPosition()
        self._stage_pos_label.setText(f"X: {x:.2f} µm Y: {y:.2f} µm")

        # add stage marker if not yet present
        if self._stage_pos_marker is None:
            self._stage_pos_marker = Markers(
                parent=self._stage_viewer.view.scene, antialias=True
            )
            self._stage_pos_marker.set_gl_state(depth_test=False)
        # update stage marker position
        self._stage_pos_marker.set_data(
            symbol="cross_lines",
            edge_color="#3A3",  # same as rgba(51, 170, 51, 255) used in SS_TOOLBUTTON
            size=50,
            edge_width=7,
            pos=np.array([[x, y]]),
        )

        if self._auto_reset_view:
            self.reset_view()

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

    def _get_stage_marker_position(self) -> tuple[float | None, float | None]:
        """Return the stage marker position.

        NOTE: the only way to get the a vispy Markers position is to use their private
        _data['a_position'] attribute. In this method we first check if the private
        attribute is available, if not we return the current stage position.
        """
        if self._stage_pos_marker is None:
            return None, None
        try:
            # NOTE: _data is a numpy array
            x, y, _ = self._stage_pos_marker._data["a_position"][0]
        except (AttributeError, IndexError, TypeError, ValueError):
            warnings.warn(
                "Could not access the '_data' attribute of vispy Markers object. "
                "Returning the current stage position.",
                stacklevel=2,
            )
            x, y = self._mmc.getXYPosition()
        return x, y

    def _on_pixel_size_changed(self, value: float) -> None:
        """Clear the scene when the pixel size changes."""
        self._stage_viewer._pixel_size = value
        # should this be a different behavior?
        self._stage_viewer.clear_scene()

    def _on_image_snapped(self) -> None:
        """Add the snapped image to the scene."""
        # get the snapped image
        img = self._mmc.getImage()
        # get the current stage position
        x, y = self._mmc.getXYPosition()
        # move the coordinates to the center of the image
        self.add_image(img, x, y, self.flip_horizontal, self.flip_vertical)

    def _on_frame_ready(self, image: np.ndarray, event: useq.MDAEvent) -> None:
        """Add the image to the scene when frameReady event is emitted."""
        # TODO: better handle z stack (e.g. max projection?)
        x = event.x_pos if event.x_pos is not None else self._mmc.getXPosition()
        y = event.y_pos if event.y_pos is not None else self._mmc.getYPosition()
        self.add_image(image, x, y, self.flip_horizontal, self.flip_vertical)

    def _move_to_clicked_position(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice():
            return
        x, y, _, _ = self._stage_viewer.view.camera.transform.imap(event.pos)
        self._mmc.setXYPosition(x, y)
        if self._snap_on_double_click:
            self._mmc.snapImage()
