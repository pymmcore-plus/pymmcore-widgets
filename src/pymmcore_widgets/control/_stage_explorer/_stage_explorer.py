from typing import TYPE_CHECKING, cast

import numpy as np
import useq
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QAction,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from vispy.app.canvas import MouseEvent

from ._stage_viewer import StageViewer

if TYPE_CHECKING:
    from ._rois import ROIRectangle

# suppress scientific notation when printing numpy arrays
np.set_printoptions(suppress=True)


GRAY = "#666"
GREEN = "#3A3"
RESET = "Reset View"
CLEAR = "Clear View"
SNAP = "Snap on Double Click"

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

        lbl_pre = QLabel("Rotation:")
        lbl_post = QLabel("°")
        self._rotation_spin = QDoubleSpinBox()
        self._rotation_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self._rotation_spin.setRange(-360, 360)
        self._rotation_spin.setSingleStep(1)
        self._rotation_spin.setValue(0)
        self._rotation_spin.valueChanged.connect(self._on_value_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(lbl_pre, 0)
        layout.addWidget(self._rotation_spin, 0)
        layout.addWidget(lbl_post, 0)

    def _on_value_changed(self, value: float) -> None:
        self.valueChanged.emit(value)

    def value(self) -> float:
        return self._rotation_spin.value()  # type: ignore


class StageExplorer(QWidget):
    """A stage positions explorer widget.

    This widget provides a visual representation of the stage positions. The user can
    interact with the stage positions by panning and zooming the view. The user can also
    move the stage to a specific position (and, optionally, snap an image) by
    double-clicking on the view.

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
    snap_on_double_click : bool
        A boolean property that controls whether to snap an image when the user
        double-clicks on the view. By default, False.
    """

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._stage_viewer = StageViewer(self)

        # to keep track of the current scale depending on the zoom level
        self._current_scale: int = 1

        # timer for polling stage position
        self._timer_id: int | None = None

        # to store the rois
        self._rois: list[ROIRectangle] = []

        # properties
        self._snap_on_double_click: bool = False
        self._poll_stage_position: bool = False
        self._rotation: float = 0.0

        # toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet(SS_TOOLBUTTON)
        toolbar.setMovable(False)
        toolbar.setContentsMargins(0, 0, 10, 0)

        # actions
        self._clear_view_act: QAction
        self._reset_view_act: QAction
        self._snap_on_double_click_act: QAction

        ACTION_MAP = {
            # action text: (icon, color, checkable, callback)
            CLEAR: (MDI6.close, GRAY, False, self._stage_viewer.clear_scene),
            RESET: (MDI6.fullscreen, GRAY, False, self._stage_viewer.reset_view),
            SNAP: (MDI6.camera_outline, GRAY, True, self._on_setting_checked),
        }

        # create actions
        for a_text, (a_icon, color, check, callback) in ACTION_MAP.items():
            action = QAction(icon(a_icon, color=color), a_text, self, checkable=check)
            action.triggered.connect(callback)
            setattr(self, f"_{a_text.lower().replace(' ', '_')}_act", action)
            toolbar.addAction(action)

        # set initial state of actions
        self._snap_on_double_click_act.setChecked(self._snap_on_double_click)

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

        # connections core events
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)

        # connections vispy events
        self._stage_viewer.canvas.events.mouse_double_click.connect(
            self._move_to_clicked_position
        )

        self._on_sys_config_loaded()

    # -----------------------------PUBLIC METHODS-------------------------------------

    @property
    def snap_on_double_click(self) -> bool:
        """Return the snap on double click property."""
        return self._snap_on_double_click

    @snap_on_double_click.setter
    def snap_on_double_click(self, value: bool) -> None:
        """Set the snap on double click property."""
        self._snap_on_double_click = value
        self._snap_on_double_click_act.setChecked(value)

    def add_image(
        self, image: np.ndarray, x_pos: float | None = None, y_pos: float | None = None
    ) -> None:
        """Add an image to the scene considering position and rotation."""
        # TODO: expose rotation and use if affine = self._mmc.getPixelSizeAffine()
        # is not set (if equal to (1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
        rotation = 0
        matrix = self._build_image_transformation_matrix(
            x_pos=x_pos, y_pos=y_pos, rotation=rotation
        )
        # transpose matrix because vispy uses column-major order
        self._stage_viewer.add_image(image, transform=matrix.T)

    # -----------------------------PRIVATE METHODS------------------------------------

    # WIDGET ----------------------------------------------------------------------

    def _on_setting_checked(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        action_map = {
            self._snap_on_double_click_act: "snap_on_double_click",
        }
        sender = cast(QAction, self.sender())

        if value := action_map.get(sender):
            setattr(self, value, checked)

    # CORE ------------------------------------------------------------------------

    def _on_sys_config_loaded(self) -> None:
        """Clear the scene when the system configuration is loaded."""
        self._stage_viewer.clear_scene()

    def _move_to_clicked_position(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice():
            return
        # map the clicked canvas position to the stage position
        x, y, _, _ = self._stage_viewer.view.camera.transform.imap(event.pos)
        self._mmc.setXYPosition(x, y)
        # update the stage position label
        self._stage_pos_label.setText(f"X: {x:.2f} µm  Y: {y:.2f} µm")
        if self._snap_on_double_click:
            # wait for the stage to be in position before snapping an images
            self._mmc.waitForDevice(self._mmc.getXYStageDevice())
            self._mmc.snapImage()

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

    # IMAGES -----------------------------------------------------------------------

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
            self._stage_viewer.reset_view()

    def _is_visual_within_view(self, x: float, y: float) -> bool:
        """Return True if the visual is within the view, otherwise False."""
        view_rect = self._stage_viewer.view.camera.rect
        px = self._mmc.getPixelSizeUm()
        half_width = self._mmc.getImageWidth() / 2 * px
        half_height = self._mmc.getImageHeight() / 2 * px
        # NOTE: x, y is the center of the image
        vertices = [
            (x - half_width, y - half_height),
            (x + half_width, y - half_height),
            (x - half_width, y + half_height),
            (x + half_width, y + half_height),
        ]
        return all(view_rect.contains(*vertex) for vertex in vertices)

    def _build_transformation_matrix(
        self,
        x_pos: float | None = None,
        y_pos: float | None = None,
        rotation: float = 0,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> np.ndarray:
        """Return the transformation matrix.

        It takes into account the pixel size (scale), rotation, and stage position.

        For rotation and scaling, if the Micro-Manager configuration uses the default
        affine transformation (1, 0, 0, 0, 1, 0), compute the transformation based on
        the pixel size and rotation. Otherwise, apply the pixel affine transformation
        matrix specified in the Micro-Manager configuration.
        """
        pixel_size = self._mmc.getPixelSizeUm()
        affine = self._mmc.getPixelSizeAffine()
        if affine == (1, 0, 0, 0, 1, 0):
            # rotation matrix
            R = np.eye(4)
            rotation_rad = np.deg2rad(rotation)
            cos_ = np.cos(rotation_rad)
            sin_ = np.sin(rotation_rad)
            R[:2, :2] = np.array([[cos_, -sin_], [sin_, cos_]])
            # scaling matrix
            S = np.eye(4)
            S[0, 0] = pixel_size
            S[1, 1] = pixel_size
            # flip the image if required
            if self._mmc.getCameraDevice():
                S[0, 0] *= -1 if flip_x else 1
                S[1, 1] *= -1 if flip_y else 1
            RS = R @ S
        else:
            RS = np.eye(4)
            RS[:2, :3] = np.array(affine).reshape(2, 3)

        T = np.eye(4)
        x_pos = self._mmc.getXPosition() if x_pos is None else x_pos
        y_pos = self._mmc.getYPosition() if y_pos is None else y_pos
        # is not really necessary to multiply by the polarity because the stage
        # devices already inveret the coords sign if activated in Micro-Manager
        T[0, 3] += x_pos  # * x_polarity
        T[1, 3] += y_pos  # * y_polarity

        return T @ RS

    def _build_image_transformation_matrix(
        self,
        x_pos: float | None = None,
        y_pos: float | None = None,
        rotation: float = 0,
    ) -> np.ndarray:
        """Return the transformation matrix to apply to the image.

        It takes into account the pixel size (scale), rotation, and stage position.
        """
        # get the flip status
        # NOTE: this can be an issue since here we are retrieving the flip status
        # from the camera device. The cameras I have used do not directly
        # flip the image if the Transpose_Mirror option is set to 1 but others
        # might do. In this latter case we will flip the image twice and is not
        # correct. How to fix this???
        if cam := self._mmc.getCameraDevice():
            mirror_x = Keyword.Transpose_MirrorX
            mirror_y = Keyword.Transpose_MirrorY
            flip_x = self._mmc.getProperty(cam, mirror_x) == "1"
            flip_y = self._mmc.getProperty(cam, mirror_y) == "1"
        # build the transformation matrix
        T = self._build_transformation_matrix(x_pos, y_pos, rotation, flip_x, flip_y)
        # by default, vispy add the images from the bottom-left corner. We need to
        # translate by -w/2 and -h/2 so the position corresponds to the center of the
        # images. In addition, this make sure the rotation (if any) is applied around
        # the center of the image.
        T_center = np.eye(4)
        T_center[0, 3] = -self._mmc.getImageWidth() / 2
        T_center[1, 3] = -self._mmc.getImageHeight() / 2

        return T @ T_center
