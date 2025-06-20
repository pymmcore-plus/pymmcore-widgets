from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
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
from pymmcore_widgets.control._rois.roi_manager import GRAY, SceneROIManager

from ._stage_position_marker import StagePositionMarker
from ._stage_viewer import StageViewer, get_vispy_scene_bounds

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PyQt6.QtGui import QAction, QActionGroup, QKeyEvent
    from qtpy.QtCore import QTimerEvent
    from vispy.app.canvas import MouseEvent

    from ._stage_viewer import VisualNode
else:
    from qtpy.QtWidgets import QAction, QActionGroup

# suppress scientific notation when printing numpy arrays
np.set_printoptions(suppress=True)


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
    QToolButton:checked {
        background-color: rgba(51, 170, 51, 255);
        border: 1px solid rgba(102, 102, 102, 80);
        border-radius: 5px;
    }
    QToolButton:!checked {
        border: 1px solid rgba(102, 102, 102, 80);
        border-radius: 5px;
    }
    QToolButton:checked:hover {
        background-color: rgba(51, 170, 51, 180);
    }
    QToolButton:!checked:hover {
        background-color: rgba(102, 102, 102, 80);
    }
"""


class PositionIndicatorMenu(QMenu):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_group = group = QActionGroup(self)
        group.setExclusive(True)
        for icon, mode in (
            (
                QIconifyIcon("ic:outline-check-box-outline-blank"),
                PositionIndicator.RECTANGLE,
            ),
            (QIconifyIcon("ic:baseline-plus"), PositionIndicator.CENTER),
            (QIconifyIcon("ic:outline-add-box"), PositionIndicator.BOTH),
        ):
            action = cast("QAction", group.addAction(icon, mode.value))
            action.setCheckable(True)
            action.setIconVisibleInMenu(True)
        self.addActions(group.actions())


class StageExplorerToolbar(QToolBar):
    """A custom toolbar for the StageExplorer widget.

    This toolbar contains actions to control the stage explorer, such as zooming to fit,
    snapping images, and showing the current stage position.
    """

    if TYPE_CHECKING:

        def addAction(self, icon: QIcon, text: str) -> QAction: ...

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setIconSize(QSize(20, 20))
        self.setMovable(False)
        self.setContentsMargins(0, 0, 10, 0)
        # self.setStyleSheet(SS_TOOLBUTTON)

        self.clear_action = self.addAction(
            QIconifyIcon("mdi:close", color=GRAY),
            "Clear View",
        )
        self.zoom_to_fit_action = self.addAction(
            QIconifyIcon("mdi:fullscreen", color=GRAY),
            "Zoom to Fit",
        )
        self.auto_zoom_to_fit_action = self.addAction(
            QIcon(str(Path(__file__).parent / "auto_zoom_to_fit_icon.svg")),
            "Auto Zoom to Fit",
        )
        self.auto_zoom_to_fit_action.setCheckable(True)
        self.snap_action = self.addAction(
            QIconifyIcon("mdi:camera-outline", color=GRAY),
            "Snap on Double Click",
        )
        self.snap_action.setCheckable(True)
        self.poll_stage_action = self.addAction(
            QIconifyIcon("mdi:map-marker-outline", color=GRAY),
            "Show FOV Position",
        )
        self.poll_stage_action.setCheckable(True)
        poll_btn = cast("QToolButton", self.widgetForAction(self.poll_stage_action))

        # menu that can be shown on right-click
        menu = PositionIndicatorMenu(self)
        self.marker_mode_action_group = menu.action_group
        poll_btn.setMenu(menu)
        poll_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        self.show_grid_action = self.addAction(
            QIconifyIcon("mdi:grid", color=GRAY),
            "Show Grid",
        )
        self.show_grid_action.setCheckable(True)
        self.delete_rois_action = self.addAction(
            QIconifyIcon("mdi:vector-square-remove", color=GRAY),
            "Delete All ROIs",
        )
        self.scan_action = self.addAction(
            QIconifyIcon("ph:path-duotone", color=GRAY),
            "Scan Selected ROIs",
        )


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
        self._mmc.events.roiSet.connect(self._on_roi_changed)

        device = self._mmc.getXYStageDevice()
        self._stage_controller = QStageMoveAccumulator.for_device(device, self._mmc)

        self._stage_viewer = StageViewer(self)
        self._stage_viewer.setCursor(Qt.CursorShape.CrossCursor)
        self.roi_manager = SceneROIManager(self._stage_viewer.canvas)

        # properties
        self._auto_zoom_to_fit: bool = False
        self._snap_on_double_click: bool = True
        self._poll_stage_position: bool = True
        self._our_mda_running: bool = False

        # stage position marker mode
        self._position_indicator: PositionIndicator = PositionIndicator.BOTH

        # timer for polling stage position
        self._timer_id: int | None = None
        # marker for stage position
        w, h = self._mmc.getImageWidth(), self._mmc.getImageHeight()
        self._stage_pos_marker: StagePositionMarker = StagePositionMarker(
            parent=self._stage_viewer.view.scene,
            rect_width=w,
            rect_height=h,
            marker_symbol_size=min((w, h)) / 10,
        )
        self._stage_pos_marker.visible = False

        # toolbar
        self._toolbar = tb = StageExplorerToolbar()

        tb.clear_action.triggered.connect(self._stage_viewer.clear)
        tb.zoom_to_fit_action.triggered.connect(self._on_zoom_to_fit_action)
        tb.auto_zoom_to_fit_action.triggered.connect(self._on_auto_zoom_to_fit_action)
        tb.snap_action.triggered.connect(self._on_snap_action)
        tb.poll_stage_action.triggered.connect(self._on_poll_stage_action)
        tb.show_grid_action.triggered.connect(self._on_show_grid_action)
        tb.delete_rois_action.triggered.connect(self._remove_rois)
        tb.scan_action.triggered.connect(self._on_scan_action)
        tb.marker_mode_action_group.triggered.connect(self._set_marker_mode)

        self._toolbar.addActions(self.roi_manager.mode_actions.actions())

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

        self._on_sys_config_loaded()
        self._on_roi_changed()

        self._toolbar.poll_stage_action.trigger()
        self.zoom_to_fit()

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
        self._toolbar.auto_zoom_to_fit_action.setChecked(value)
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
        self._toolbar.snap_action.setChecked(value)

    @property
    def poll_stage_position(self) -> bool:
        """Whether to continually show the current stage position."""
        return self._poll_stage_position

    @poll_stage_position.setter
    def poll_stage_position(self, value: bool) -> None:
        """Set the poll stage position property."""
        self._poll_stage_position = value
        self._toolbar.poll_stage_action.setChecked(value)
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
        visuals: Iterable[VisualNode] = [
            *self._stage_viewer._get_images(),  # pyright: ignore
            self._stage_pos_marker,
        ]
        x_bounds, y_bounds, *_ = get_vispy_scene_bounds(visuals)
        self._stage_viewer.view.camera.set_range(x=x_bounds, y=y_bounds, margin=margin)

    # -----------------------------PRIVATE METHODS------------------------------------

    # ACTIONS ----------------------------------------------------------------------

    def _on_roi_changed(self) -> None:
        """Update the ROI manager when a new ROI is set."""
        fov_w, fov_h, z_pos = self._fov_w_h_z_pos()
        self.roi_manager.update_fovs((fov_w, fov_h))
        # update stage marker size
        fov_w = self._mmc.getImageWidth()
        fov_h = self._mmc.getImageHeight()
        self._stage_pos_marker.set_rect_size(fov_w, fov_h)

    def _on_snap_action(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        self.snap_on_double_click = checked

    def _on_zoom_to_fit_action(self, checked: bool) -> None:
        """Set the zoom to fit property based on the state of the action."""
        # self._toolbar.zoom_to_fit_action.setChecked(checked)
        self._auto_zoom_to_fit = False
        self.zoom_to_fit()

    def _on_auto_zoom_to_fit_action(self, checked: bool) -> None:
        """Set the auto zoom to fit property based on the state of the action."""
        self._auto_zoom_to_fit = checked
        if checked:
            self.zoom_to_fit()

    def _set_marker_mode(self) -> None:
        """Update the poll mode and show/hide the required stage position marker.

        Usually, the sender will be the action_group on the _PollStageCtxMenu.
        """
        sender = self.sender()
        if isinstance(sender, QActionGroup) and (action := sender.checkedAction()):
            self._position_indicator = PositionIndicator(action.text())

        self._stage_pos_marker.set_rect_visible(self._position_indicator.show_rect)
        self._stage_pos_marker.set_marker_visible(self._position_indicator.show_marker)

    def _remove_rois(self) -> None:
        """Delete all the ROIs."""
        self.roi_manager.clear()

    def _on_scan_action(self) -> None:
        """Scan the selected ROIs."""
        if not (active_rois := self.roi_manager.selected_rois()):
            return
        active_roi = active_rois[0]
        fov_w, fov_h, z_pos = self._fov_w_h_z_pos()
        if plan := active_roi.create_grid_plan(fov_w=fov_w, fov_h=fov_h):
            seq = useq.MDASequence(stage_positions=list(plan))

            if not self._mmc.mda.is_running():
                self._our_mda_running = True
                self._mmc.run_mda(seq)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is None:
            return
        if a0.key() == Qt.Key.Key_Escape:
            if self._our_mda_running:
                self._mmc.mda.cancel()
                self._our_mda_running = False
        super().keyPressEvent(a0)

    # CORE ------------------------------------------------------------------------

    def _fov_w_h_z_pos(self) -> tuple[float, float, float]:
        """Return the field of view width, height and z position."""
        px = self._mmc.getPixelSizeUm()
        fov_w = self._mmc.getImageWidth() * px
        fov_h = self._mmc.getImageHeight() * px
        z_pos = self._mmc.getZPosition()
        return fov_w, fov_h, z_pos

    def _on_sys_config_loaded(self) -> None:
        """Clear the scene when the system configuration is loaded."""
        self._stage_viewer.clear()

    def _on_pixel_size_changed(self, value: float) -> None:
        """Update scene when the pixel size changes."""
        ...

    def _on_mouse_double_click(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice():
            return
        if self.roi_manager.mode == "create-poly":
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
        self._stage_pos_marker.visible = checked
        print("Stage position marker visible:", self._stage_pos_marker.visible)
        self._poll_stage_position = checked
        if checked:
            self._timer_id = self.startTimer(20)
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None

    def _on_show_grid_action(self, checked: bool) -> None:
        """Set the show grid property based on the state of the action."""
        self._stage_viewer.set_grid_visible(checked)
        # self._toolbar.show_grid_action.setChecked(checked)

    def timerEvent(self, event: QTimerEvent) -> None:
        """Poll the stage position."""
        if not self._mmc.getXYStageDevice():
            self._stage_pos_label.setText("No XY stage device")
            return

        # update the stage position label
        stage_x, stage_y = self._mmc.getXYPosition()
        self._stage_pos_label.setText(f"X: {stage_x:.2f} µm  Y: {stage_y:.2f} µm")

        # build the stage marker affine using the affine matrix since we need to take
        # into account the rotation and scaling
        matrix = self._build_stage_marker_complete_affine_matrix(stage_x, stage_y)

        # IMPORTANT!
        # the transform we apply here *also* includes the pixel size scaling, along
        # with the rotation and translation. That's why the stage position marker
        # does not account for pixel size scaling.  This needs to be standardized
        # unified somewhere.

        # update stage marker position
        self._stage_pos_marker.apply_transform(matrix.T)
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
