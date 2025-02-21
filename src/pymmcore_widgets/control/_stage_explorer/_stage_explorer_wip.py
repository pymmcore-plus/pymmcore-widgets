from typing import cast

import numpy as np
import useq
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimerEvent, Signal
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
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Rectangle

from ._stage_viewer_wip import StageViewer

# suppress scientific notation when printing numpy arrays
np.set_printoptions(suppress=True)


GRAY = "#666"
GREEN = "#3A3"
RESET = "Reset View"
CLEAR = "Clear View"
SNAP = "Snap on Double Click"
POLL_STAGE = "Poll Stage Position"
SEPARATOR = "Separator"
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

        lbl_pre = QLabel("Rotation:")
        lbl_post = QLabel("°")
        self._rotation_spin = QDoubleSpinBox()
        self._rotation_spin.setRange(-360, 360)
        self._rotation_spin.setSingleStep(1)
        self._rotation_spin.setValue(0)
        self._rotation_spin.valueChanged.connect(self._on_value_changed)

        wdg = QWidget()
        layout = QHBoxLayout(wdg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(lbl_pre, 0)
        layout.addWidget(self._rotation_spin, 0)
        layout.addWidget(lbl_post, 0)

        toolbar = QToolBar()
        toolbar.setStyleSheet(SS_TOOLBUTTON)
        toolbar.setMovable(False)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(wdg)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(toolbar)

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
    poll_stage_position : bool
        A boolean property that controls whether to poll the stage position.
        If True, the widget will poll the stage position and display the current X and Y
        coordinates in the status bar and with a 'cross_lines' marker. If False, the
        widget will stop polling the stage position. By default, False.
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
        self._poll_stage_position_act: QAction

        ACTION_MAP = {
            # action text: (icon, color, checkable, callback)
            CLEAR: (MDI6.close, GRAY, False, self.clear_scene),
            RESET: (MDI6.fullscreen, GRAY, False, self.reset_view),
            SNAP: (MDI6.camera_outline, GRAY, True, self._on_setting_checked),
            POLL_STAGE: (MDI6.map_marker, GRAY, True, self._on_poll_stage),
            f"{SEPARATOR}1": (None, None, None, None),
        }

        # create actions
        for a_text, (a_icon, color, check, callback) in ACTION_MAP.items():
            if SEPARATOR in a_text:
                toolbar.addSeparator()
                continue
            action = QAction(icon(a_icon, color=color), a_text, self, checkable=check)
            action.triggered.connect(callback)
            setattr(self, f"_{a_text.lower().replace(' ', '_')}_act", action)
            toolbar.addAction(action)

        # set initial state of actions
        self._snap_on_double_click_act.setChecked(self._snap_on_double_click)
        self._poll_stage_position_act.setChecked(self._poll_stage_position)

        # add rotation control to the toolbar
        self._rotation_control = RotationControl()
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

        # marker for stage position
        self._stage_pos_marker = self._init_stage_position_marker(self._mmc)
        # to store stage xy position. used in timerEvent
        self._xy: tuple[float | None, float | None] = (None, None)

        # connect vispy events
        self._stage_viewer.canvas.events.mouse_double_click.connect(
            self._move_to_clicked_position
        )
        # connect rotation control
        self._rotation_control.valueChanged.connect(self._update_stage_marker)
        # connections core events
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.events.pixelSizeChanged.connect(self._on_pixel_size_changed)
        self._mmc.events.roiSet.connect(self._update_stage_marker)

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
        self, image: np.ndarray, x_pos: float | None = None, y_pos: float | None = None
    ) -> None:
        """Add an image to the scene considering position and rotation."""
        affine = self._mmc.getPixelSizeAffine()
        rotation = self._rotation_control.value() if affine == (1, 0, 0, 0, 1, 0) else 0
        matrix = self._build_image_transformation_matrix(
            x_pos=x_pos, y_pos=y_pos, rotation=rotation
        )
        # transpose matrix because vispy uses column-major order
        self._stage_viewer.add_image(image, transform=matrix.T)

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
        self._update_stage_marker()
        self.reset_view()

    # def value(self) -> list[useq.Position]:
    #     """Return a list of `GridFromEdges` objects from the drawn rectangles."""
    #     rects = self._stage_viewer.rects
    #     positions = []
    #     px = self._mmc.getPixelSizeUm()
    #     fov_w, fov_h = self._mmc.getImageWidth() * px, self._mmc.getImageHeight() * px
    #     for rct in rects:
    #         x, y = rct.center
    #         w, h = rct.width, rct.height
    #         grid_plan = useq.GridFromEdges(
    #             top=y + h / 2,
    #             bottom=y - h / 2,
    #             left=x - w / 2,
    #             right=x + w / 2,
    #             fov_width=fov_w,
    #             fov_height=fov_h,
    #         )
    #         pos = useq.AbsolutePosition(
    #             x=x,
    #             y=y,
    #             z=self._mmc.getZPosition(),
    #             sequence=useq.MDASequence(grid_plan=grid_plan),
    #         )
    #         positions.append(pos)
    #     return positions

    # -----------------------------PRIVATE METHODS------------------------------------

    # CORE ------------------------------------------------------------------------
    def _on_sys_config_loaded(self) -> None:
        """Clear the scene when the system configuration is loaded."""
        self.clear_scene()

    def _on_pixel_size_changed(self) -> None:
        """Update the stage position marker when the pixel size changes."""
        self._stage_viewer.pixel_size = self._mmc.getPixelSizeUm()
        self._update_stage_marker()

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
            # wait for the stage to be in position before snapping an image
            self._mmc.waitForDevice(self._mmc.getXYStageDevice())
            self._mmc.snapImage()

    # WIDGET ----------------------------------------------------------------------

    def _on_setting_checked(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        action_map = {
            self._snap_on_double_click_act: "snap_on_double_click",
        }
        sender = cast(QAction, self.sender())

        if value := action_map.get(sender):
            setattr(self, value, checked)

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
            self.reset_view()

    def _build_transformation_matrix(
        self,
        x_pos: float | None = None,
        y_pos: float | None = None,
        rotation: float = 0,
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
            RS = R @ S
        else:
            RS = np.eye(4)
            RS[:2, :3] = np.array(affine).reshape(2, 3)

        # flip the image if the camera has transpose mirror options enabled
        if (cam := self._mmc.getCameraDevice()) is not None:
            flip_h = 1 if self._mmc.getProperty(cam, "Transpose_MirrorX") == 1 else -1
            flip_v = 1 if self._mmc.getProperty(cam, "Transpose_MirrorY") == 1 else -1
            RS[0, 0] *= flip_h
            RS[1, 1] *= flip_v

        T = np.eye(4)
        x_pos = self._mmc.getXPosition() if x_pos is None else x_pos
        y_pos = self._mmc.getYPosition() if y_pos is None else y_pos
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
        # TODO: add support for flipping images using the mirror transpose camera option
        # build scale and rotation matrix
        T = self._build_transformation_matrix(x_pos, y_pos, rotation)
        # by default, vispy add the images from the bottom-left corner. We need to
        # translate by -w/2 and -h/2 so the position corresponds to the center of the
        # images. In addition, make sure the rotation is applied around the center of
        # the image.
        T_center = np.eye(4)
        T_center[0, 3] = -self._mmc.getImageWidth() / 2
        T_center[1, 3] = -self._mmc.getImageHeight() / 2

        print(T @ T_center)
        return T @ T_center

    # STAGE MARKER ----------------------------------------------------------------

    def _init_stage_position_marker(self, mmc: CMMCorePlus) -> Rectangle | None:
        """Initialize the stage position marker."""
        if not mmc.getXYStageDevice():
            return None
        rect = Rectangle(
            parent=self._stage_viewer.view.scene,
            center=(0, 0),
            width=self._mmc.getImageWidth(),
            height=self._mmc.getImageHeight(),
            border_width=4,
            border_color=GREEN,
            color=None,
        )
        rect.set_gl_state(depth_test=False)
        rect.visible = False
        return rect

    def _update_stage_marker(
        self, x_pos: float | None = None, y_pos: float | None = None
    ) -> None:
        """Update the stage position marker."""
        if self._stage_pos_marker is None:
            return
        # build transformation matrix
        T = self._build_transformation_matrix(
            x_pos, y_pos, self._rotation_control.value()
        )
        self._stage_pos_marker.transform = scene.MatrixTransform(matrix=T.T)

    def _on_poll_stage(self, checked: bool) -> None:
        """Set the poll stage position property based on the state of the action."""
        self._poll_stage_position = checked
        if checked:
            self._timer_id = self.startTimer(50)
            if self._stage_pos_marker is not None:
                self._stage_pos_marker.visible = True
                self.reset_view()
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
            if self._stage_pos_marker is not None:
                self._stage_pos_marker.visible = False

    def timerEvent(self, event: QTimerEvent) -> None:
        """Poll the stage position."""
        if not self._mmc.getXYStageDevice():
            return

        x, y = self._mmc.getXYPosition()

        # update the stage position label
        self._stage_pos_label.setText(f"X: {x:.2f} µm  Y: {y:.2f} µm")

        # update stage marker position
        if self._stage_pos_marker is not None:
            self._update_stage_marker(x, y)

        # compare the old and new xy positions; if the percentage difference exceeds 5%,
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
        matrix = self._stage_pos_marker.transform.matrix
        x, y = matrix[:2, 3]
        w, h = self._stage_pos_marker.width, self._stage_pos_marker.height
        min_x, min_y = x - w / 2, y - h / 2
        max_x, max_y = x + w / 2, y + h / 2
        return min_x, min_y, max_x, max_y

    def _is_visual_within_view(self, x: float, y: float) -> bool:
        """Return True if the visual is within the view, otherwise False."""
        view_rect = self._stage_viewer.view.camera.rect
        px = self._mmc.getPixelSizeUm()
        half_width = self._mmc.getImageWidth() / 2 * px
        half_height = self._mmc.getImageHeight() / 2 * px
        vertices = [
            (x - half_width, y - half_height),
            (x + half_width, y - half_height),
            (x - half_width, y + half_height),
            (x + half_width, y + half_height),
        ]
        return all(view_rect.contains(*vertex) for vertex in vertices)
