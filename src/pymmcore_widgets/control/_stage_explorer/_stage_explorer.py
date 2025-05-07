from __future__ import annotations

import contextlib
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

import numpy as np
import useq
import vispy.scene
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QIcon, QKeyEvent, QKeySequence, QUndoCommand, QUndoStack
from qtpy.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets.control._q_stage_controller import QStageMoveAccumulator

from ._rois import ROIRectangle
from ._stage_position_marker import StagePositionMarker
from ._stage_viewer import StageViewer, get_vispy_scene_bounds

if TYPE_CHECKING:
    from PyQt6.QtGui import QAction, QActionGroup
    from qtpy.QtCore import QTimerEvent
    from vispy.app.canvas import MouseEvent
    from vispy.scene.visuals import VisualNode
else:
    from qtpy.QtWidgets import QAction, QActionGroup

# suppress scientific notation when printing numpy arrays
np.set_printoptions(suppress=True)


GRAY = "#666"
ZOOM_TO_FIT = "Zoom to Fit"
AUTO_ZOOM_TO_FIT = "Auto Zoom to Fit"
AUTO_ZOOM_TO_FIT_ICON = QIcon(str(Path(__file__).parent / "auto_zoom_to_fit_icon.svg"))
CLEAR = "Clear View"
SNAP = "Snap on Double Click"
POLL_STAGE = "Show FOV Position"
SHOW_GRID = "Show Grid"
ROIS = "Activate/Deactivate ROIs Tool"
DELETE_ROIS = "Delete All ROIs"


# this might belong in _stage_position_marker.py
class PositionIndicator(str, Enum):
    """Way in which the stage position is indicated."""

    RECTANGLE = "FOV Rectangle"
    CENTER = "FOV Center"
    BOTH = "Both"

    def __str__(self) -> str:
        return self.value

    @property
    def show_rect(self) -> bool:
        """Whether to show the rectangle."""
        return self in (self.RECTANGLE, self.BOTH)

    @property
    def show_marker(self) -> bool:
        """Whether to show the marker."""
        return self in (self.CENTER, self.BOTH)


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


class _RoiCommand(QUndoCommand):
    def __init__(self, explorer: StageExplorer, roi: ROIRectangle) -> None:
        super().__init__("Add ROI")
        self._explorer = explorer
        self._roi = roi


class InsertRoiCommand(_RoiCommand):
    def undo(self) -> None:
        self._explorer._remove_roi(self._roi)

    def redo(self) -> None:
        self._explorer._add_roi(self._roi)


class DeleteRoiCommand(_RoiCommand):
    def undo(self) -> None:
        self._explorer._add_roi(self._roi)

    def redo(self) -> None:
        self._explorer._remove_roi(self._roi)


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
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(10)
        self._undo_act = self._undo_stack.createUndoAction(self, "&Undo")
        self._undo_act.triggered.connect(lambda: print("Undo triggered"))
        self._undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        self._redo_act = self._undo_stack.createRedoAction(self, "&Redo")
        self._redo_act.setShortcut(QKeySequence.StandardKey.Redo)

        device = self._mmc.getXYStageDevice()
        self._stage_controller = QStageMoveAccumulator.for_device(device, self._mmc)

        self._stage_viewer = StageViewer(self)
        self._stage_viewer.setCursor(Qt.CursorShape.CrossCursor)

        self._grid_lines = vispy.scene.GridLines(
            parent=self._stage_viewer.view.scene,
            color="#888888",
            border_width=1,
        )
        self._grid_lines.visible = False

        # to keep track of the current scale depending on the zoom level
        self._current_scale: int = 1

        # properties
        self._auto_zoom_to_fit: bool = False
        self._snap_on_double_click: bool = False
        self._poll_stage_position: bool = True
        # to store the rois
        self._rois: set[ROIRectangle] = set()

        # stage position marker mode
        self._position_indicator: PositionIndicator = PositionIndicator.BOTH

        # timer for polling stage position
        self._timer_id: int | None = None
        # marker for stage position
        self._stage_pos_marker: StagePositionMarker | None = None

        # toolbar
        self._toolbar = QToolBar()
        self._toolbar.setStyleSheet(SS_TOOLBUTTON)
        self._toolbar.setMovable(False)
        self._toolbar.setContentsMargins(0, 0, 10, 0)

        # actions
        self._actions: dict[str, QAction] = {}

        # fmt: off
        # {text: (icon, checkable, on_triggered)}
        ACTION_MAP: dict[str, tuple[str | QIcon, bool, Callable]] = {
            CLEAR: ("mdi:close", False, self._stage_viewer.clear),
            ZOOM_TO_FIT: ("mdi:fullscreen", False, self._on_zoom_to_fit_action),
            AUTO_ZOOM_TO_FIT: (AUTO_ZOOM_TO_FIT_ICON, True, self._on_auto_zoom_to_fit_action),  # noqa: E501
            SNAP: ("mdi:camera-outline", True, self._on_snap_action),
            POLL_STAGE: ("mdi:map-marker-outline", True, self._on_poll_stage_action),
            SHOW_GRID: ("mdi:grid", True, self._on_show_grid_action),
            ROIS: ("mdi:vector-square", True, None),
            DELETE_ROIS: ("mdi:vector-square-remove", False, self._remove_rois),
        }
        # fmt: on

        # create actions
        for a_text, (icon, check, callback) in ACTION_MAP.items():
            if isinstance(icon, str):
                icon = QIconifyIcon(icon, color=GRAY)
            self._actions[a_text] = action = QAction(icon, a_text, self)
            action.setCheckable(check)
            if callback is not None:
                action.triggered.connect(callback)

            if a_text == POLL_STAGE:
                # create special toolbutton with a context menu on right-click
                btn = self._create_poll_stage_button()
                btn.setDefaultAction(action)
                self._toolbar.addWidget(btn)
                action.setChecked(self._poll_stage_position)
                self._on_poll_stage_action(self._poll_stage_position)
            else:
                self._toolbar.addAction(action)

        # add stage pos label to the toolbar
        self._stage_pos_label = QLabel()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toolbar.addWidget(spacer)
        self._toolbar.addWidget(self._stage_pos_label)

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._toolbar, 0)
        main_layout.addWidget(self._stage_viewer, 1)

        # connections core events
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.events.pixelSizeChanged.connect(self._on_pixel_size_changed)

        # connections vispy events
        self._stage_viewer.canvas.events.mouse_double_click.connect(
            self._on_mouse_double_click
        )

        # connections vispy events for ROIs
        self._stage_viewer.canvas.events.mouse_press.connect(self._on_mouse_press)
        self._stage_viewer.canvas.events.mouse_move.connect(self._on_mouse_move)
        self._stage_viewer.canvas.events.mouse_release.connect(self._on_mouse_release)

        self._on_sys_config_loaded()

    # -----------------------------PUBLIC METHODS-------------------------------------

    def toolBar(self) -> QToolBar:
        """Return the toolbar of the widget."""
        return self._toolbar

    @property
    def auto_zoom_to_fit(self) -> bool:
        """Whether to automatically zoom to fit the full scene in the view.

        When True, the view will automatically zoom to fit the full scene
        when a new image is added or when the stage position marker moves
        out of view.
        """
        return self._auto_zoom_to_fit

    @auto_zoom_to_fit.setter
    def auto_zoom_to_fit(self, value: bool) -> None:
        self._auto_zoom_to_fit = value
        self._actions[ZOOM_TO_FIT].setChecked(value)
        if value:
            self.zoom_to_fit()

    @property
    def snap_on_double_click(self) -> bool:
        """Whether to snap an image on double click.

        When True, the widget will snap an image when the user double-clicks
        on the view, after the stage has moved to the clicked position.
        """
        return self._snap_on_double_click

    @snap_on_double_click.setter
    def snap_on_double_click(self, value: bool) -> None:
        self._snap_on_double_click = value
        self._actions[SNAP].setChecked(value)

    @property
    def poll_stage_position(self) -> bool:
        """Whether to continually show the current stage position."""
        return self._poll_stage_position

    @poll_stage_position.setter
    def poll_stage_position(self, value: bool) -> None:
        """Set the poll stage position property."""
        self._poll_stage_position = value
        self._actions[POLL_STAGE].setChecked(value)
        self._on_poll_stage_action(value)

    @property
    def rois(self) -> list[ROIRectangle]:
        """List of ROIs in the scene."""
        return self._rois

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

    def value(self) -> list[useq.Position]:
        """Return a list of `GridFromEdges` objects from the drawn rectangles."""
        # TODO: add a way to set overlap
        positions = []
        px = self._mmc.getPixelSizeUm()
        fov_w, fov_h = self._mmc.getImageWidth() * px, self._mmc.getImageHeight() * px
        for rect in self._rois:
            grid_plan = self._build_grid_plan(rect, fov_w, fov_h)
            if isinstance(grid_plan, useq.AbsolutePosition):
                positions.append(grid_plan)
            else:
                x, y = rect.center
                pos = useq.AbsolutePosition(
                    x=x,
                    y=y,
                    z=self._mmc.getZPosition(),
                    sequence=useq.MDASequence(grid_plan=grid_plan),
                )
                positions.append(pos)
        return positions

    # -----------------------------PRIVATE METHODS------------------------------------

    # ACTIONS ----------------------------------------------------------------------

    def _on_snap_action(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        self.snap_on_double_click = checked

    def _on_zoom_to_fit_action(self, checked: bool) -> None:
        """Set the zoom to fit property based on the state of the action."""
        self._actions[AUTO_ZOOM_TO_FIT].setChecked(False)
        self._auto_zoom_to_fit = False
        self.zoom_to_fit()

    def _on_auto_zoom_to_fit_action(self, checked: bool) -> None:
        """Set the auto zoom to fit property based on the state of the action."""
        self._auto_zoom_to_fit = checked
        if checked:
            self.zoom_to_fit()

    def _create_poll_stage_button(self) -> QToolButton:
        btn = QToolButton()
        btn.setToolTip(f"{POLL_STAGE} (right-click for marker options)")

        # menu that can be shown on right-click
        menu = _PollStageCtxMenu(btn)
        menu.setIndicator(self._position_indicator)
        menu.action_group.triggered.connect(self._set_poll_mode)

        # connect right click to show the menu
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(menu.show_at_position)
        return btn

    def _set_poll_mode(self) -> None:
        """Update the poll mode and show/hide the required stage position marker.

        Usually, the sender will be the action_group on the _PollStageCtxMenu.
        """
        sender = self.sender()
        if isinstance(sender, QActionGroup) and (action := sender.checkedAction()):
            self._position_indicator = PositionIndicator(action.text())

        if self._stage_pos_marker is not None:
            self._stage_pos_marker.set_rect_visible(self._position_indicator.show_rect)
            self._stage_pos_marker.set_marker_visible(
                self._position_indicator.show_marker
            )

    def _on_show_grid_action(self, checked: bool) -> None:
        """Set the show grid property based on the state of the action."""
        self._grid_lines.visible = checked
        self._actions[SHOW_GRID].setChecked(checked)

    def _remove_rois(self) -> None:
        """Delete all the ROIs."""
        while self._rois:
            roi = self._rois.pop()
            self._remove_roi(roi)

    # CORE ------------------------------------------------------------------------

    def _on_sys_config_loaded(self) -> None:
        """Clear the scene when the system configuration is loaded."""
        self._stage_viewer.clear()

    def _on_pixel_size_changed(self, value: float) -> None:
        """Clear the scene when the pixel size changes."""
        self._delete_stage_position_marker()

    def _on_mouse_double_click(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice():
            return

        # map the clicked canvas position to the stage position
        x, y, _, _ = self._stage_viewer.view.camera.transform.imap(event.pos)
        self._stage_controller.move_absolute((x, y))
        self._stage_controller.snap_on_finish = self._snap_on_double_click

        # update the stage position label
        self._stage_pos_label.setText(f"X: {x:.2f} µm  Y: {y:.2f} µm")
        # snap an image if the snap on double click property is set

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
            self._timer_id = self.startTimer(20)
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
            self._delete_stage_position_marker()

    def _delete_stage_position_marker(self) -> None:
        """Delete the stage position marker."""
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.parent = None
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
        if (mk := self._stage_pos_marker) is None:
            mk = self._create_stage_pos_marker()

        # update stage marker position
        mk.apply_transform(matrix.T)
        # zoom_to_fit only if auto _auto_zoom_to_fit property is set to True.
        # NOTE: this could be slightly annoying...  might need a sub-option?
        if self._auto_zoom_to_fit:
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

    def _create_stage_pos_marker(self) -> StagePositionMarker:
        """Create a marker at the current stage position."""
        w, h = self._mmc.getImageWidth(), self._mmc.getImageHeight()
        self._stage_pos_marker = StagePositionMarker(
            parent=self._stage_viewer.view.scene,
            rect_width=w,
            rect_height=h,
            marker_symbol_size=min((w, h)) / 10,
        )
        # update the marker state depending on the selected poll mode
        self._set_poll_mode()
        # reset if the view is empty (only the stage marker is present)
        if not list(self._stage_viewer._get_images()):
            self.zoom_to_fit()

        return self._stage_pos_marker

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

    # ROIs ------------------------------------------------------------------------

    def _active_roi(self) -> ROIRectangle | None:
        """Return the next active ROI."""
        return next((roi for roi in self._rois if roi.selected()), None)

    def _on_mouse_press(self, event: MouseEvent) -> None:
        """Handle the mouse press event."""
        canvas_pos = (event.pos[0], event.pos[1])

        picked = None
        for roi in self._rois:
            if not picked and (grb := roi.obj_at_pos(event.pos)) is not None:
                roi.anchor_at(grb, event.pos)
                roi.set_selected(True)
                picked = roi
            else:
                roi.set_selected(False)

        if self._active_roi() is not None:
            self._stage_viewer.view.camera.interactive = False

        # (button = 1 is left mouse button)
        elif self._actions[ROIS].isChecked() and event.button == 1:
            self._stage_viewer.view.camera.interactive = False
            # create the ROI rectangle for the first time
            roi = self._create_roi(canvas_pos)
            self._undo_stack.push(InsertRoiCommand(self, roi))

    def _create_roi(self, canvas_pos: tuple[float, float]) -> ROIRectangle:
        """Create a new ROI rectangle and connect its events."""
        roi = ROIRectangle(self._stage_viewer.view.scene)
        world_pos = roi._tform().map(canvas_pos)[:2]
        roi.visible = True
        roi.set_selected(True)
        roi.set_anchor(world_pos)
        # roi.set_bounding_box(world_pos, world_pos)
        return roi

    def _on_mouse_move(self, event: MouseEvent) -> None:
        """Update the roi text when the roi changes size."""
        if (roi := self._active_roi()) is not None:
            # set cursor
            cursor = roi.get_cursor(event)
            self._stage_viewer.canvas.native.setCursor(cursor)
            # update roi text
            px = self._mmc.getPixelSizeUm()
            fov_w = self._mmc.getImageWidth() * px
            fov_h = self._mmc.getImageHeight() * px
            grid_plan = self._build_grid_plan(roi, fov_w, fov_h)
            try:
                pos = list(grid_plan)
                rows = max(r.row for r in pos if r.row is not None) + 1
                cols = max(c.col for c in pos if c.col is not None) + 1
                roi.set_text(f"r{rows} x c{cols}")
            except AttributeError:
                roi.set_text("r1 x c1")
        else:
            # reset cursor to default
            self._stage_viewer.canvas.native.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        self._stage_viewer.view.camera.interactive = True

        # if alt key is not down...
        if QApplication.keyboardModifiers() != Qt.KeyboardModifier.AltModifier:
            # set the roi to not selected
            self._actions[ROIS].setChecked(False)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is None:  # pragma: no cover
            return

        # if key is alt, activate rois tool
        if a0.key() == Qt.Key.Key_Alt and not self._actions[ROIS].isChecked():
            self._actions[ROIS].setChecked(True)
        # if key is del or cancel, remove the selected roi
        elif a0.key() == Qt.Key.Key_Backspace:
            self._remove_selected_roi()
        elif a0.key() == Qt.Key.Key_V:
            print(self.value())
        elif a0.key() == Qt.Key.Key_Z:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self._undo_stack.undo()
            elif (
                a0.modifiers()
                == Qt.KeyboardModifier.ShiftModifier
                | Qt.KeyboardModifier.ControlModifier
            ):
                self._undo_stack.redo()
        else:  # pragma: no cover
            super().keyPressEvent(a0)

    def keyReleaseEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is not None:
            if a0.key() == Qt.Key.Key_Alt and self._actions[ROIS].isChecked():
                self._actions[ROIS].setChecked(False)
            else:
                super().keyReleaseEvent(a0)

    def _remove_selected_roi(self) -> None:
        """Delete the selected ROI from the scene."""
        if (roi := self._active_roi()) is not None:
            self._undo_stack.push(DeleteRoiCommand(self, roi))

    def _remove_roi(self, roi: ROIRectangle) -> None:
        """Delete the selected ROI from the scene."""
        if roi in self._rois:
            roi.parent = None
            self._rois.remove(roi)
            with contextlib.suppress(Exception):
                roi.disconnect(self._stage_viewer.canvas)

    def _add_roi(self, roi: ROIRectangle) -> None:
        roi.parent = self._stage_viewer.view.scene
        roi.connect(self._stage_viewer.canvas)
        self._rois.add(roi)

    # GRID PLAN -------------------------------------------------------------------

    def _build_grid_plan(
        self, roi: ROIRectangle, fov_w: float, fov_h: float
    ) -> useq.GridFromEdges | useq.AbsolutePosition:
        """Return a `GridFromEdges` plan from the roi and fov width and height."""
        top_left, bottom_right = roi.bounding_box()

        # if the width and the height of the roi are smaller than the fov width and
        # height, return a single position at the center of the roi and not a grid plan.
        w = bottom_right[0] - top_left[0]
        h = bottom_right[1] - top_left[1]
        if w < fov_w and h < fov_h:
            return useq.AbsolutePosition(
                x=top_left[0] + (w / 2),
                y=top_left[1] + (h / 2),
                z=self._mmc.getZPosition(),
            )
        # NOTE: we need to add the fov_w/2 and fov_h/2 to the top_left and
        # bottom_right corners respectively because the grid plan is created
        # considering the center of the fov and we want the roi to define the edges
        # of the grid plan.
        return useq.GridFromEdges(
            top=top_left[1] - (fov_h / 2),
            bottom=bottom_right[1] + (fov_h / 2),
            left=top_left[0] + (fov_w / 2),
            right=bottom_right[0] - (fov_w / 2),
            fov_width=fov_w,
            fov_height=fov_h,
        )


class _PollStageCtxMenu(QMenu):
    """Custom context menu for the poll stage position button.

    The menu contains options to select the type of marker to display (rectangle,
    center, or both).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.action_group = group = QActionGroup(self)
        group.setExclusive(True)

        for mode in PositionIndicator:
            action = cast("QAction", group.addAction(mode.value))
            action.setCheckable(True)

        self.addActions(group.actions())

    def setIndicator(self, mode: PositionIndicator | str) -> None:
        """Set the poll mode based on the selected action."""
        mode = PositionIndicator(mode)
        action = next(action for action in self.actions() if action.text() == mode)
        action.setChecked(True)

    def show_at_position(self, pos: QPoint) -> None:
        """Show the poll stage position context menu at the given global position.

        If a button is the sender, the position is mapped to global coordinates.
        """
        if isinstance(sender := self.sender(), QWidget):
            pos = sender.mapToGlobal(pos)
        self.exec(pos)
