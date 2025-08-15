from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QModelIndex, QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)
from superqt import QEnumComboBox, QIconifyIcon
from useq import OrderMode

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
        background-color: rgba(51, 170, 51, 180);
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
    QToolButton[popupMode="1"] {
        padding-right: 8px;
    }
    QToolButton::menu-button {
        border: 3px solid transparent;
        border-left: 1px solid  rgba(102, 102, 102, 80);
        width: 8px;
    }
    QToolButton::menu-arrow {
        width: 8px;
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
        self._mmc.events.roiSet.connect(self._on_roi_changed)

        xy_device = self._mmc.getXYStageDevice()
        self._stage_controller = QStageMoveAccumulator.for_device(xy_device, self._mmc)

        self._stage_viewer = StageViewer(self)
        self._stage_viewer.setCursor(Qt.CursorShape.CrossCursor)
        self.roi_manager = SceneROIManager(self._stage_viewer.canvas)

        # properties
        self._auto_zoom_to_fit: bool = False
        self._snap_on_double_click: bool = True
        self._poll_stage_position: bool = True
        self._our_mda_running: bool = False
        self._grid_overlap: float = 0.0
        self._grid_mode: OrderMode = OrderMode.row_wise_snake

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

        # --- cached parameters for efficient affine calculations ---
        self._affine_state = AffineState(self._mmc)

        # toolbar and actions
        self._toolbar = tb = StageExplorerToolbar()
        # (also add the actions from the ROI manager)
        self._toolbar.insertActions(
            tb.delete_rois_action, self.roi_manager.mode_actions.actions()
        )
        # add stage pos label to the toolbar
        self._stage_pos_label = QLabel()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toolbar.addWidget(spacer)
        self._toolbar.addWidget(self._stage_pos_label)

        # connect actions to methods
        tb.clear_action.triggered.connect(self._stage_viewer.clear)
        tb.zoom_to_fit_action.triggered.connect(self._on_zoom_to_fit_action)
        tb.auto_zoom_to_fit_action.triggered.connect(self._on_auto_zoom_to_fit_action)
        tb.snap_action.triggered.connect(self._on_snap_action)
        tb.poll_stage_action.triggered.connect(self._on_poll_stage_action)
        tb.show_grid_action.triggered.connect(self._on_show_grid_action)
        tb.delete_rois_action.triggered.connect(self.roi_manager.clear)
        tb.scan_action.triggered.connect(self._on_scan_action)
        tb.marker_mode_action_group.triggered.connect(self._update_marker_mode)
        tb.scan_menu.valueChanged.connect(self._on_scan_options_changed)
        # ensure newly-created ROIs inherit the current scan menu settings
        self.roi_manager.roi_model.rowsInserted.connect(self._on_roi_rows_inserted)

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
        self._mmc.events.pixelSizeAffineChanged.connect(
            self._on_pixel_size_affine_changed
        )

        # connections vispy events
        self._stage_viewer.canvas.events.mouse_double_click.connect(
            self._on_mouse_double_click
        )

        # initial setup
        self._on_sys_config_loaded()
        self._on_roi_changed()
        self._toolbar.snap_action.setChecked(self._snap_on_double_click)
        self._toolbar.poll_stage_action.trigger()
        self.zoom_to_fit()

    # -----------------------------PUBLIC METHODS-------------------------------------

    def toolBar(self) -> StageExplorerToolbar:
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
        stage_shift = np.eye(4)
        stage_shift[0:2, 3] = (stage_x_um, stage_y_um)
        # TODO: it's a little odd we apply half_img_shift here, but not in the
        # stage position marker... figure that out.
        matrix = stage_shift @ self._affine_state.system_affine @ self._half_img_shift
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

    def rois_to_useq_positions(self) -> list[useq.AbsolutePosition] | None:
        if not (rois := self.roi_manager.all_rois()):
            return None

        positions: list[useq.AbsolutePosition] = []
        for idx, roi in enumerate(rois):
            overlap, mode = self._toolbar.scan_menu.value()
            if plan := roi.create_grid_plan(*self._fov_w_h(), overlap, mode):
                p: useq.AbsolutePosition = next(iter(plan.iter_grid_positions()))
                pos = useq.AbsolutePosition(
                    name=f"ROI_{idx}",
                    x=p.x,
                    y=p.y,
                    z=p.z,
                    sequence=useq.MDASequence(grid_plan=plan),
                )
                positions.append(pos)

        if not positions:
            return None

        return positions

    # -----------------------------PRIVATE METHODS------------------------------------

    # ACTIONS ----------------------------------------------------------------------

    def _on_roi_changed(self) -> None:
        """Update the ROI manager when a new ROI is set."""
        img_w = self._mmc.getImageWidth()
        img_h = self._mmc.getImageHeight()
        px = self._mmc.getPixelSizeUm()
        self.roi_manager.update_fovs((img_w * px, img_h * px))

        # by default, vispy add the images from the bottom-left corner. We need to
        # translate by -w/2 and -h/2 so the position corresponds to the center of the
        # images. In addition, this makes sure the rotation (if any) is applied around
        # the center of the image.
        self._half_img_shift = np.eye(4)
        self._half_img_shift[0:2, 3] = (-img_w / 2, -img_h / 2)

        self._stage_pos_marker.set_rect_size(img_w, img_h)

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

    def _update_marker_mode(self) -> None:
        """Update the poll mode and show/hide the required stage position marker.

        Usually, the sender will be the action_group on the PositionIndicatorMenu.
        """
        sender = self.sender()
        if isinstance(sender, QActionGroup) and (action := sender.checkedAction()):
            pi = PositionIndicator(action.text())
            self._stage_pos_marker.set_rect_visible(pi.show_rect)
            self._stage_pos_marker.set_marker_visible(pi.show_marker)

    def _on_scan_action(self) -> None:
        """Scan the selected ROI."""
        if not (active_rois := self.roi_manager.selected_rois()):
            return
        active_roi = active_rois[0]

        overlap, mode = self._toolbar.scan_menu.value()
        if plan := active_roi.create_grid_plan(*self._fov_w_h(), overlap, mode):
            seq = useq.MDASequence(grid_plan=plan)
            if not self._mmc.mda.is_running():
                self._our_mda_running = True
                self._mmc.run_mda(seq)

    def _on_scan_options_changed(self, value: tuple[float, OrderMode]) -> None:
        """Update all ROIs with the new overlap so the vispy visuals refresh."""
        # store locally in case callers want to use it
        self._grid_overlap, self._grid_mode = value

        # update ROIs and emit model dataChanged so visuals update
        for roi in self.roi_manager.all_rois():
            roi.fov_overlap = (self._grid_overlap, self._grid_overlap)
            roi.scan_order = self._grid_mode
            self.roi_manager.roi_model.emitDataChange(roi)

    def _on_roi_rows_inserted(self, parent: QModelIndex, first: int, last: int) -> None:
        """Initialize newly-inserted ROIs with the current scan menu values.

        This ensures ROIs created after adjusting the scan options start with the
        chosen overlap and acquisition order.
        """
        overlap, mode = self._toolbar.scan_menu.value()
        for row in range(first, last + 1):
            roi = self.roi_manager.roi_model.index(row).internalPointer()
            roi.fov_overlap = (overlap, overlap)
            roi.acq_mode = mode
            self.roi_manager.roi_model.emitDataChange(roi)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is None:
            return
        if a0.key() == Qt.Key.Key_Escape:
            if self._our_mda_running:
                self._mmc.mda.cancel()
                self._our_mda_running = False
        super().keyPressEvent(a0)

    # CORE ------------------------------------------------------------------------

    def _fov_w_h(self) -> tuple[float, float]:
        """Return the field of view width and height."""
        px = self._mmc.getPixelSizeUm()
        fov_w = self._mmc.getImageWidth() * px
        fov_h = self._mmc.getImageHeight() * px
        return fov_w, fov_h

    def _half_img_translation_mtx(self, img_w: int, img_h: int) -> np.ndarray:
        """Return the transformation matrix to translate half the size of the image."""
        # by default, vispy add the images from the bottom-left corner. We need to
        # translate by -w/2 and -h/2 so the position corresponds to the center of the
        # images. In addition, this make sure the rotation (if any) is applied around
        # the center of the image.
        T_center = np.eye(4)
        T_center[0, 3] = -img_w / 2
        T_center[1, 3] = -img_h / 2
        return T_center

    def _on_sys_config_loaded(self) -> None:
        """Clear the scene when the system configuration is loaded."""
        self._stage_viewer.clear()

    def _on_pixel_size_changed(self, value: float) -> None:
        """Update scene when the pixel size changes."""
        self._affine_state.refresh()

    def _on_pixel_size_affine_changed(self) -> None:
        """Handle updates to the 2 x 3 pixel size affine."""
        self._pixel_size_affine = self._mmc.getPixelSizeAffine()
        self._affine_state.refresh()

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
        self._poll_stage_position = checked
        if checked:
            self._timer_id = self.startTimer(20)
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None

    def _on_show_grid_action(self, checked: bool) -> None:
        """Set the show grid property based on the state of the action."""
        self._stage_viewer.set_grid_visible(checked)

    def timerEvent(self, event: QTimerEvent | None) -> None:
        """Poll the stage position."""
        if not self._mmc.getXYStageDevice():
            self._stage_pos_label.setText("No XY stage device")
            return

        # update the stage position label
        stage_x, stage_y = self._mmc.getXYPosition()
        self._stage_pos_label.setText(f"X: {stage_x:.2f} µm  Y: {stage_y:.2f} µm")

        # fast path: copy cached rotation/scale part and just update translation
        matrix = self._affine_state.system_affine_translated(stage_x, stage_y)
        self._stage_pos_marker.apply_transform(matrix.T)

        # zoom_to_fit only if auto _auto_zoom_to_fit property is set to True.
        # NOTE: this could be slightly annoying...  might need a sub-option?
        if self._auto_zoom_to_fit:
            self.zoom_to_fit()

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
        fov_w, fov_h = self._fov_w_h()
        half_width = fov_w / 2
        half_height = fov_h / 2
        # NOTE: x, y is the center of the image
        vertices = [
            (x - half_width, y - half_height),  # bottom-left
            (x + half_width, y - half_height),  # bottom-right
            (x - half_width, y + half_height),  # top-left
            (x + half_width, y + half_height),  # top-right
        ]
        return all(view_rect.contains(*vertex) for vertex in vertices)


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
        self.setIconSize(QSize(22, 22))
        # self.setMovable(False)
        self.setContentsMargins(0, 0, 8, 0)
        self.setStyleSheet(SS_TOOLBUTTON)

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
        self.addSeparator()
        self.delete_rois_action = self.addAction(
            QIconifyIcon("mdi:vector-square-remove", color=GRAY),
            "Delete All ROIs",
        )
        self.addSeparator()
        self.scan_action = self.addAction(
            QIconifyIcon("ph:path-duotone", color=GRAY),
            "Scan Selected ROI",
        )
        scan_btn = cast("QToolButton", self.widgetForAction(self.scan_action))
        self.scan_menu = ScanMenu(self)
        scan_btn.setMenu(self.scan_menu)
        scan_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)


class ScanMenu(QMenu):
    """Menu widget that exposes scan grid options."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setTitle("Scan Selected ROI")

        # container widget for form layout
        opts_widget = QWidget(self)
        form = QFormLayout(opts_widget)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        # overlap spinbox
        self._overlap_spin = QDoubleSpinBox(opts_widget)
        self._overlap_spin.setDecimals(2)
        self._overlap_spin.setRange(-100, 100)
        self._overlap_spin.setSingleStep(1)
        form.addRow("Overlap", self._overlap_spin)

        # acquisition mode combo
        self._mode_cbox = QEnumComboBox(self, OrderMode)
        self._mode_cbox.setCurrentEnum(OrderMode.row_wise_snake)
        form.addRow("Order", self._mode_cbox)

        # wrap in a QWidgetAction so it shows as a menu panel
        self.opts_action = QWidgetAction(self)
        self.opts_action.setDefaultWidget(opts_widget)
        self.addAction(self.opts_action)

        self._overlap_spin.valueChanged.connect(self._on_value_changed)
        self._mode_cbox.currentTextChanged.connect(self._on_value_changed)

    def value(self) -> tuple[float, useq.OrderMode]:
        """Return the current grid overlap and order mode."""
        return self._overlap_spin.value(), cast(
            "OrderMode", self._mode_cbox.currentEnum()
        )

    def _on_value_changed(self) -> None:
        self.valueChanged.emit(self.value())


SLOTS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**SLOTS)
class AffineState:
    """Cached state for the affine transformation of the stage viewer.

    Call refresh() to recompute the state based on the current camera settings.
    """

    mmc: CMMCorePlus
    pixel_size_um: float = field(init=False)
    pixel_size_affine: tuple[float, ...] = field(init=False)
    system_affine: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.refresh()

    # Public

    def refresh(self) -> None:
        """Recompute everything that depends on camera settings."""
        self.pixel_size_um = self.mmc.getPixelSizeUm()
        self.pixel_size_affine = self.mmc.getPixelSizeAffine()
        self.system_affine = self._compute_system_affine()

    def system_affine_translated(self, x: float, y: float) -> np.ndarray:
        """Return the system affine matrix translated to the given (x, y) position."""
        # fast path: copy cached rotation/scale part and just update translation
        matrix = self.system_affine.copy()
        matrix[0:2, 3] = (x, y)
        return matrix

    # Private helpers

    def _compute_system_affine(self) -> np.ndarray:
        flip_x = flip_y = False
        if cam := self.mmc.getCameraDevice():
            flip_x = self.mmc.getProperty(cam, Keyword.Transpose_MirrorX) == "1"
            flip_y = self.mmc.getProperty(cam, Keyword.Transpose_MirrorY) == "1"

        if self._pixel_config_is_identity():
            return self._linear_matrix(flip_x, flip_y)
        return self._pixel_config_matrix(flip_x, flip_y)

    def _linear_matrix(
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
        S = np.diag([self.pixel_size_um, self.pixel_size_um, 1, 1])
        # flip the image if required
        if flip_x:
            S[0, 0] *= -1
        if flip_y:
            S[1, 1] *= -1
        return R @ S  # type: ignore[no-any-return]

    def _pixel_config_is_identity(self) -> bool:
        return np.allclose(self.pixel_size_affine, (1.0, 0.0, 0.0, 0.0, 1.0, 0.0))

    def _pixel_config_matrix(
        self, flip_x: bool = False, flip_y: bool = False
    ) -> np.ndarray:
        """Return the current pixel configuration affine, if set.

        If the pixel configuration is not set (i.e. is the identity matrix),
        it will return None.
        """
        tform = np.eye(4)
        tform[:2, :3] = np.array(self.pixel_size_affine).reshape(2, 3)
        # flip the image if required
        # TODO: Should this ALWAYS be done?
        if flip_x:
            tform[0, 0] *= -1
        if flip_y:
            tform[1, 1] *= -1
        return tform
