from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtWidgets import (
    QAction,
    QLabel,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

from ._stage_viewer import StageViewer

if TYPE_CHECKING:
    import useq
    from vispy.app.canvas import MouseEvent


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
        self._rezoom_on_new_image: bool = True

        # to keep track of the current scale depending on the zoom level
        self._current_scale: int = 1

        # timer for polling stage position
        self._timer_id: int | None = None

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
            CLEAR: (MDI6.close, GRAY, False, self._stage_viewer.clear),
            RESET: (MDI6.fullscreen, GRAY, False, self._stage_viewer.zoom_to_fit),
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
        self, image: np.ndarray, stage_x_um: float, stage_y_um: float
    ) -> None:
        """Add an image to the scene at a give (x, y) stage position in microns."""
        # TODO: expose rotation and use if affine = self._mmc.getPixelSizeAffine()
        # is not set (if equal to (1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
        matrix = self._create_complete_affine_matrix(x_pos=stage_x_um, y_pos=stage_y_um)
        self._stage_viewer.add_image(image, transform=matrix.T)

    # -----------------------------PRIVATE METHODS------------------------------------

    # WIDGET ----------------------------------------------------------------------

    def _on_setting_checked(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        action_map = {
            self._snap_on_double_click_act: "snap_on_double_click",
        }
        sender = cast("QAction", self.sender())

        if value := action_map.get(sender):
            setattr(self, value, checked)

    # CORE ------------------------------------------------------------------------

    def _on_sys_config_loaded(self) -> None:
        """Clear the scene when the system configuration is loaded."""
        self._stage_viewer.clear()

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
        self, image: np.ndarray, stage_x_um: float, stage_y_um: float
    ) -> None:
        """Add the image to the scene and update position label and view.

        (called by _on_image_snapped and _on_frame_ready).
        """
        self.add_image(image, stage_x_um, stage_y_um)

        # update the stage position label if the stage position is not being polled
        if not self._poll_stage_position:
            self._stage_pos_label.setText(
                f"X: {stage_x_um:.2f} µm  Y: {stage_y_um:.2f} µm"
            )

        # reset the view if the image is not within the view
        if (
            not self._is_visual_within_view(stage_x_um, stage_y_um)
            and self._rezoom_on_new_image
        ):
            self._stage_viewer.zoom_to_fit()

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

    def _create_complete_affine_matrix(self, x_pos: float, y_pos: float) -> np.ndarray:
        """Construct affine matrix for the current state of the system + stage position.

        This method combines the system affine matrix (if set) with a translation
        according to the provided stage position. The resulting matrix can be passed
        to the `add_image` method of the `StageViewer` class to position the image
        correctly in the scene.
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

        # Create the complete matrix
        # 1. translate_half the image width
        half_img_shift = self._t_half_width()

        # 2. get the affine transform from the core configuration, or
        # fallback to a manually constructed one if not set
        system_affine = self._current_pixel_config_affine()
        if system_affine is None:
            system_affine = self._build_linear_matrix(0, flip_x, flip_y)

        # 3. translate to the stage position
        stage_shift = np.eye(4)
        stage_shift[0:2, 3] = (x_pos, y_pos)

        # 1. translate_half_width -> 2. rotate/scale -> 3. translate_to_stage_pos
        # (reminder: the order of the matrix multiplication is reversed :)
        return stage_shift @ system_affine @ half_img_shift  # type: ignore

    def _current_pixel_config_affine(self) -> np.ndarray | None:
        """Return the current pixel configuration affine, if set.

        If the pixel configuration is not set (i.e. is the identity matrix),
        it will return None.
        """
        affine = self._mmc.getPixelSizeAffine()
        # TODO: determine whether this is the best way to check if this info is
        # available or not.
        if np.allclose(affine, (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)):
            return None

        tform = np.eye(4)
        tform[:2, :3] = np.array(affine).reshape(2, 3)
        return tform

    def _build_linear_matrix(
        self, rotation: float = 0, flip_x: bool = False, flip_y: bool = False
    ) -> np.ndarray:
        """Build linear transformation matrix for rotation and scaling.

        The matrix is still 4x4, but has no translation component.
        """
        # rotation matrix
        R = np.eye(4)
        rotation_rad = np.deg2rad(rotation)
        cos_ = np.cos(rotation_rad)
        sin_ = np.sin(rotation_rad)
        R[:2, :2] = np.array([[cos_, -sin_], [sin_, cos_]])
        # scaling matrix
        pixel_size = self._mmc.getPixelSizeUm()
        S = np.eye(4)
        S[0, 0] = pixel_size
        S[1, 1] = pixel_size
        # flip the image if required
        if self._mmc.getCameraDevice():
            S[0, 0] *= -1 if flip_x else 1
            S[1, 1] *= -1 if flip_y else 1
        return R @ S

    def _t_half_width(self) -> np.ndarray:
        """Return the transformation matrix to translate half the size of the image."""
        # by default, vispy add the images from the bottom-left corner. We need to
        # translate by -w/2 and -h/2 so the position corresponds to the center of the
        # images. In addition, this make sure the rotation (if any) is applied around
        # the center of the image.
        T_center = np.eye(4)
        T_center[0, 3] = -self._mmc.getImageWidth() / 2
        T_center[1, 3] = -self._mmc.getImageHeight() / 2
        return T_center
