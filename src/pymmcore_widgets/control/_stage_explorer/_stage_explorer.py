from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QAction,
    QActionGroup,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from ._stage_position_marker import StagePositionMarker
from ._stage_viewer import StageViewer, get_vispy_scene_bounds

if TYPE_CHECKING:
    import useq
    from qtpy.QtCore import QTimerEvent
    from vispy.app.canvas import MouseEvent
    from vispy.scene.visuals import VisualNode


# suppress scientific notation when printing numpy arrays
np.set_printoptions(suppress=True)


GRAY = "#666"
ZOOM_TO_FIT = "Zoom to Fit"
AUTO_ZOOM_TO_FIT = "Auto Zoom to Fit"
AUTO_ZOOM_TO_FIT_ICON = QIcon(str(Path(__file__).parent / "auto_zoom_to_fit_icon.svg"))
CLEAR = "Clear View"
SNAP = "Snap on Double Click"
POLL_STAGE = "Poll Stage Position"
RECT_MODE = "FOV Rectangle"
CENTER_MODE = "FOV Center"
BOTH_MODE = "Both"

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
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].

    Properties
    ----------
    auto_zoom_to_fit : bool
        A boolean property that controls whether to automatically "zoom to fit"
        the view when a new image is added to the scene or when the position of the
        stage marker (if enabled) is out of view. By default, False.
        By default, False.
    snap_on_double_click : bool
        A boolean property that controls whether to snap an image when the user
        double-clicks on the view. By default, False.
    poll_stage_position : bool
        A boolean property that controls whether to poll the stage position.
        If True, the widget will poll the stage position and display a rectangle
        around the current stage position. By default, False.
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

        # properties
        self._auto_zoom_to_fit: bool = False
        self._snap_on_double_click: bool = False
        self._poll_stage_position: bool = False

        # poll mode to select the stage position marker type
        self._poll_mode: str = BOTH_MODE

        # timer for polling stage position
        self._timer_id: int | None = None
        # marker for stage position
        self._stage_pos_marker: StagePositionMarker | None = None

        # toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet(SS_TOOLBUTTON)
        toolbar.setMovable(False)
        toolbar.setContentsMargins(0, 0, 10, 0)

        # actions
        self._clear_view_act: QAction
        self._zoom_to_fit_act: QAction
        self._auto_zoom_to_fit_act: QAction
        self._snap_on_double_click_act: QAction
        self._poll_stage_position_act: QAction

        # fmt: off
        ACTION_MAP = {
            # action text: (icon, color, checkable, callback)
            CLEAR: ("mdi:close", GRAY, False, self._stage_viewer.clear),
            ZOOM_TO_FIT: ("mdi:fullscreen", GRAY, False, self.zoom_to_fit),
            AUTO_ZOOM_TO_FIT: (AUTO_ZOOM_TO_FIT_ICON, GRAY, True, self._on_auto_zoom_to_fit_action),  # noqa: E501
            SNAP: ("mdi:camera-outline", GRAY, True, self._on_snap_action),
            POLL_STAGE: ("mdi:map-marker-outline", GRAY, True, self._on_poll_stage_action),  # noqa: E501
        }

        # create actions
        for a_text, (a_icon, color, check, callback) in ACTION_MAP.items():
            ic = a_icon if isinstance(a_icon, QIcon) else QIconifyIcon(a_icon, color=color)  # noqa: E501
            action = QAction(ic, a_text, self, checkable=check)
            action.triggered.connect(callback)
            setattr(self, f"_{a_text.lower().replace(' ', '_')}_act", action)
            # add a QToolButton to the toolbar if the action is "Poll Stage" so we can
            # set up a context menu
            if a_text == POLL_STAGE:
                btn = QToolButton(self)
                btn.setDefaultAction(action)
                self._setup_poll_stage_context_menu(btn)
                btn.setToolTip(f"{POLL_STAGE} (right-click for marker options)")
                self._setup_poll_stage_context_menu(btn)
                toolbar.addWidget(btn)
            else:
                toolbar.addAction(action)
        # fmt: on

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
        self._mmc.events.pixelSizeChanged.connect(self._on_pixel_size_changed)

        # connections vispy events
        self._stage_viewer.canvas.events.mouse_double_click.connect(
            self._move_to_clicked_position
        )

        self._on_sys_config_loaded()

    # -----------------------------PUBLIC METHODS-------------------------------------

    @property
    def auto_zoom_to_fit(self) -> bool:
        """Return the auto zoom to fit property."""
        return self._auto_zoom_to_fit

    @auto_zoom_to_fit.setter
    def auto_zoom_to_fit(self, value: bool) -> None:
        """Set the auto zoom to fit property."""
        self._auto_zoom_to_fit = value
        self._auto_zoom_to_fit_act.setChecked(value)
        if value:
            self.zoom_to_fit()

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
        self._on_poll_stage_action(value)

    def add_image(
        self, image: np.ndarray, stage_x_um: float, stage_y_um: float
    ) -> None:
        """Add an image to the scene at a give (x, y) stage position in microns."""
        # TODO: expose rotation and use if affine = self._mmc.getPixelSizeAffine()
        # is not set (if equal to (1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
        matrix = self._create_complete_affine_matrix(x_pos=stage_x_um, y_pos=stage_y_um)
        self._stage_viewer.add_image(image, transform=matrix.T)

    def zoom_to_fit(self, *, margin: float = 0.05) -> None:
        """Zoom to fit the current view to the images in the scene.

        ...also considering the stage position marker.
        """
        visuals: list[VisualNode] = list(self._stage_viewer._get_images())
        if self._stage_pos_marker is not None:
            visuals.append(self._stage_pos_marker)
        x_bounds, y_bounds, *_ = get_vispy_scene_bounds(visuals)
        self._stage_viewer.view.camera.set_range(x=x_bounds, y=y_bounds, margin=margin)

    # -----------------------------PRIVATE METHODS------------------------------------

    # ACTIONS ----------------------------------------------------------------------

    def _on_snap_action(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        self.snap_on_double_click = checked

    def _on_auto_zoom_to_fit_action(self, checked: bool) -> None:
        """Set the auto zoom to fit property based on the state of the action."""
        self._auto_zoom_to_fit = checked
        if checked:
            self.zoom_to_fit()

    def _setup_poll_stage_context_menu(self, button: QToolButton) -> None:
        # Allow custom context menu
        button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Connect the signal
        button.customContextMenuRequested.connect(
            lambda pos: self._show_poll_stage_menu(button.mapToGlobal(pos))
        )

    def _show_poll_stage_menu(self, global_pos: QPoint) -> None:
        # create exclusive action group for the poll mode
        group = QActionGroup(self)
        group.setExclusive(True)

        action_fov_rect = QAction(RECT_MODE, self, checkable=True)
        action_fov_center = QAction(CENTER_MODE, self, checkable=True)
        action_both = QAction(BOTH_MODE, self, checkable=True)

        group.addAction(action_fov_rect)
        group.addAction(action_fov_center)
        group.addAction(action_both)

        # set checked state based on current mode
        if self._poll_mode == RECT_MODE:
            action_fov_rect.setChecked(True)
        elif self._poll_mode == CENTER_MODE:
            action_fov_center.setChecked(True)
        else:
            action_both.setChecked(True)

        # connect actions
        action_fov_rect.triggered.connect(lambda: self._set_poll_mode(RECT_MODE))
        action_fov_center.triggered.connect(lambda: self._set_poll_mode(CENTER_MODE))
        action_both.triggered.connect(lambda: self._set_poll_mode(BOTH_MODE))

        menu = QMenu()
        menu.addActions(group.actions())
        menu.exec(global_pos)

    def _set_poll_mode(self, mode: str) -> None:
        """Update the poll mode and show/hide the required stage position marker."""
        self._poll_mode = mode

        if self._stage_pos_marker is None:
            return

        visibility = {
            BOTH_MODE: (True, True),
            RECT_MODE: (True, False),
            CENTER_MODE: (False, True),
        }
        show_rect, show_marker = visibility.get(mode, (False, False))
        self._stage_pos_marker.show_rectangle(show_rect)
        self._stage_pos_marker.show_marker(show_marker)

    # CORE ------------------------------------------------------------------------

    def _on_sys_config_loaded(self) -> None:
        """Clear the scene when the system configuration is loaded."""
        self._stage_viewer.clear()

    def _on_pixel_size_changed(self, value: float) -> None:
        """Clear the scene when the pixel size changes."""
        self._delete_stage_position_marker()

    def _move_to_clicked_position(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice():
            return

        # map the clicked canvas position to the stage position
        x, y, _, _ = self._stage_viewer.view.camera.transform.imap(event.pos)
        self._mmc.setXYPosition(x, y)
        # update the stage position label
        self._stage_pos_label.setText(f"X: {x:.2f} µm  Y: {y:.2f} µm")
        # snap an image if the snap on double click property is set
        if self._snap_on_double_click:
            # wait for the stage to be in position before continuing
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

    # STAGE POSITION MARKER -----------------------------------------------------

    def _on_poll_stage_action(self, checked: bool) -> None:
        """Set the poll stage position property based on the state of the action."""
        self._poll_stage_position = checked
        if checked:
            self._timer_id = self.startTimer(10)
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
            self._delete_stage_position_marker()

    def _delete_stage_position_marker(self) -> None:
        """Delete the stage position marker."""
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.delete_stage_marker()
            self._stage_pos_marker = None

    def timerEvent(self, event: QTimerEvent) -> None:
        """Poll the stage position."""
        if not self._mmc.getXYStageDevice():
            self._stage_pos_label.setText("No XY stage device")
            return

        stage_x, stage_y = self._mmc.getXYPosition()

        # update the stage position label
        self._stage_pos_label.setText(f"X: {stage_x:.2f} µm  Y: {stage_y:.2f} µm")

        # build the stage marker affine using the affine matrix since we need to take
        # into account the rotation and scaling
        matrix = self._build_stage_marker_complete_affine_matrix(stage_x, stage_y)

        # create stage marker if not yet present
        if self._stage_pos_marker is None:
            self._create_stage_pos_marker()

        # update stage marker position
        mk = cast("StagePositionMarker", self._stage_pos_marker)
        mk.applyTransform(matrix.T)

        # zoom_to_fit only if the stage position marker is out of view
        # (and the auto _auto_zoom_to_fit property is set to True)
        if self._auto_zoom_to_fit and self._is_stage_marker_out_of_view():
            self.zoom_to_fit()

    def _build_stage_marker_complete_affine_matrix(
        self, stage_x: float, stage_y: float
    ) -> np.ndarray:
        """Build the affine matrix for the stage position marker.

        We need this to take into account any rotation (but do not need to flip or shift
        the position half the width and height since the marker is already centered).
        """
        system_affine = self._current_pixel_config_affine()
        if system_affine is None:
            system_affine = self._build_linear_matrix(0)
        stage_shift = np.eye(4)
        stage_shift[0:2, 3] = (stage_x, stage_y)
        return stage_shift @ system_affine  # type: ignore

    def _create_stage_pos_marker(self) -> None:
        """Create a marker at the current stage position."""
        w, h = self._mmc.getImageWidth(), self._mmc.getImageHeight()
        self._stage_pos_marker = StagePositionMarker(
            parent=self._stage_viewer.view.scene,
            center=(0, 0),
            rect_width=w,
            rect_height=h,
            rect_color="#3A3",
            rect_thickness=4,
            show_rect=True,
            marker_symbol="++",
            marker_symbol_color="#3A3",
            marker_symbol_size=min((w, h)) / 10,
            marker_symbol_edge_width=10,
            show_marker_symbol=True,
        )
        # update the marker state depending on the selected poll mode
        self._set_poll_mode(self._poll_mode)
        # reset if the view is empty (only the stage marker is present)
        if not list(self._stage_viewer._get_images()):
            self.zoom_to_fit()

    def _is_stage_marker_out_of_view(self) -> bool:
        """Return True if the stage position marker center is out of view."""
        if self._stage_pos_marker is None:
            return False

        # marker center in local coords
        cx, cy = self._stage_pos_marker.center

        # transform to world/scene coords
        print(self._stage_pos_marker.transform)
        world_center = self._stage_pos_marker.transform.map([[cx, cy]])[0, :2]

        # get visible view rectangle from camera
        view = self._stage_viewer.view
        view_left, view_bottom = view.camera.rect.left, view.camera.rect.bottom
        view_right = view_left + view.camera.rect.width
        view_top = view_bottom + view.camera.rect.height

        # check if center is outside the visible rectangle
        x, y = world_center
        return bool(x < view_left or x > view_right or y < view_bottom or y > view_top)

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
            and self._auto_zoom_to_fit
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
            (x - half_width, y - half_height),  # bottom-left
            (x + half_width, y - half_height),  # bottom-right
            (x - half_width, y + half_height),  # top-left
            (x + half_width, y + half_height),  # top-right
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
        system_affine = self._current_pixel_config_affine(flip_x, flip_y)
        if system_affine is None:
            system_affine = self._build_linear_matrix(0, flip_x, flip_y)

        # 3. translate to the stage position
        stage_shift = np.eye(4)
        stage_shift[0:2, 3] = (x_pos, y_pos)

        # 1. translate_half_width -> 2. rotate/scale -> 3. translate_to_stage_pos
        # (reminder: the order of the matrix multiplication is reversed :)
        return stage_shift @ system_affine @ half_img_shift  # type: ignore

    def _current_pixel_config_affine(
        self, flip_x: bool = False, flip_y: bool = False
    ) -> np.ndarray | None:
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
        # flip the image if required
        # TODO: Should this ALWAYS be done?
        if flip_x:
            tform[0, 0] *= -1
        if flip_y:
            tform[1, 1] *= -1
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
        if flip_x:
            S[0, 0] *= -1
        if flip_y:
            S[1, 1] *= -1
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
