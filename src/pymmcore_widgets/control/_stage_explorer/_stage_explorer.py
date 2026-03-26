from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QSize, Qt, QThread, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)
from superqt import QEnumComboBox, QIconifyIcon, QLabeledRangeSlider
from useq import OrderMode

from pymmcore_widgets.control._q_stage_controller import QStageMoveAccumulator
from pymmcore_widgets.control._rois.roi_manager import GRAY, SceneROIManager

from ._stage_position_marker import StagePositionMarker
from ._stage_viewer import StageViewer, get_vispy_scene_bounds

if TYPE_CHECKING:
    from PyQt6.QtGui import QAction, QActionGroup, QKeyEvent
    from qtpy.QtGui import QCloseEvent
    from vispy.app.canvas import MouseEvent
else:
    from qtpy.QtWidgets import QAction, QActionGroup

# suppress scientific notation when printing numpy arrays
np.set_printoptions(suppress=True)

STAGE_POLL_INTERVAL_MS = 100
STAGE_POS_TOLERANCE_UM_SQ = 0.01  # 0.1 µm squared


class _StagePoller(QThread):
    """Background thread that polls the XY stage position."""

    positionChanged = Signal(float, float)

    def __init__(self, mmc: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mmc = mmc

    def run(self) -> None:
        """Poll the stage position.

        If the stage position has changed by more than the tolerance since the last
        poll, emit the positionChanged signal with the new stage position.
        """
        last: tuple[float, float] | None = None
        while not self.isInterruptionRequested():
            if self._mmc.getXYStageDevice():
                x, y = self._mmc.getXYPosition()
                if last is not None:
                    dx, dy = x - last[0], y - last[1]
                    if dx * dx + dy * dy < STAGE_POS_TOLERANCE_UM_SQ:
                        self.msleep(STAGE_POLL_INTERVAL_MS)
                        continue
                last = (x, y)
                self.positionChanged.emit(x, y)
            self.msleep(STAGE_POLL_INTERVAL_MS)

    def stop(self) -> None:
        self.requestInterruption()
        self.wait()


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

        self._stage_controller: QStageMoveAccumulator | None = None
        self._set_stage_controller()

        self._stage_viewer = StageViewer(self)
        self._stage_viewer.setCursor(Qt.CursorShape.CrossCursor)
        self.roi_manager = SceneROIManager(self._stage_viewer.canvas)

        # properties
        self._auto_zoom_to_fit: bool = False
        self._snap_on_double_click: bool = True
        self._poll_stage_position: bool = self._has_devices()
        self._our_mda_running: bool = False

        # background thread for polling stage position
        self._stage_poller = _StagePoller(self._mmc)
        self._stage_poller.positionChanged.connect(self._on_stage_position_polled)

        # marker for stage position (created when a camera is available)
        self._stage_pos_marker: StagePositionMarker | None = None
        self._create_stage_pos_marker()

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
        tb.clear_action.triggered.connect(self._on_clear_action)
        tb.zoom_to_fit_action.triggered.connect(self._on_zoom_to_fit_action)
        tb.auto_zoom_to_fit_action.triggered.connect(self._on_auto_zoom_to_fit_action)
        tb.snap_action.triggered.connect(self._on_snap_action)
        tb.poll_stage_action.triggered.connect(self._on_poll_stage_action)
        tb.show_grid_action.triggered.connect(self._on_show_grid_action)
        tb.delete_rois_action.triggered.connect(self.roi_manager.clear)
        tb.scan_action.triggered.connect(self._on_scan_action)
        tb.marker_mode_action_group.triggered.connect(self._update_marker_mode)
        tb.scan_menu.valueChanged.connect(self._on_scan_options_changed)

        self._contrast_slider = ContrastSlider(self)
        self._contrast_slider.setVisible(False)
        self._stage_viewer.climRangeChanged.connect(self._on_clim_range_changed)
        self._contrast_slider.valueChanged.connect(self._on_contrast_slider_changed)
        self._contrast_slider.autoToggled.connect(self._on_auto_contrast_toggled)

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._toolbar, 0)
        main_layout.addWidget(self._stage_viewer, 1)
        main_layout.addWidget(self._contrast_slider, 0)

        # connections core events
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.events.pixelSizeChanged.connect(self._on_pixel_size_changed)
        self._mmc.events.pixelSizeAffineChanged.connect(self._on_pixel_size_changed)

        # connections vispy events
        self._stage_viewer.canvas.events.mouse_double_click.connect(
            self._on_mouse_double_click
        )

        # initial setup
        self._on_roi_changed()
        self._toolbar.snap_action.setChecked(self._snap_on_double_click)
        self._update_actions_enabled()
        if self._poll_stage_position:
            self._toolbar.poll_stage_action.trigger()
        self.zoom_to_fit()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self._stop_poller()
        super().closeEvent(a0)

    def __del__(self) -> None:
        self._stop_poller()

    def _stop_poller(self) -> None:
        try:
            if self._stage_poller.isRunning():
                self._stage_poller.stop()
        except RuntimeError:  # pragma: no cover
            pass

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
        # compute half-image shift from actual image dimensions so it's always
        # correct regardless of camera property changes.
        # by default, vispy add the images from the bottom-left corner. We need to
        # translate by -w/2 and -h/2 so the position corresponds to the center of the
        # images. In addition, this makes sure the rotation (if any) is applied around
        # the center of the image.
        h, w = image.shape[:2]
        half_img_shift = np.eye(4)
        half_img_shift[0:2, 3] = (-w / 2, -h / 2)

        stage_shift = np.eye(4)
        stage_shift[0:2, 3] = (stage_x_um, stage_y_um)
        matrix = stage_shift @ self._affine_state.system_affine @ half_img_shift
        self._stage_viewer.add_image(image, transform=matrix.T)

        # update the stage position marker size to match the actual image
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.set_rect_size(w, h)

    def zoom_to_fit(self, *, margin: float = 0.05) -> None:
        """Zoom to fit the current view to the images in the scene.

        ...also considering the stage position marker.
        """
        visuals: list = list(self._stage_viewer._get_images())  # pyright: ignore
        if self._stage_pos_marker is not None:
            visuals.append(self._stage_pos_marker)
        x_bounds, y_bounds, *_ = get_vispy_scene_bounds(visuals)
        self._stage_viewer.view.camera.set_range(x=x_bounds, y=y_bounds, margin=margin)

    # -----------------------------PRIVATE METHODS------------------------------------

    def _has_devices(self) -> bool:
        """Return True if devices (beyond the core) are loaded."""
        return len(self._mmc.getLoadedDevices()) > 1

    def _update_actions_enabled(self) -> None:
        """Enable/disable toolbar actions based on loaded devices."""
        has_devices = self._has_devices()
        tb = self._toolbar
        tb.snap_action.setEnabled(has_devices)
        tb.poll_stage_action.setEnabled(has_devices)
        tb.scan_action.setEnabled(has_devices)
        tb.delete_rois_action.setEnabled(has_devices)
        for action in self.roi_manager.mode_actions.actions():
            action.setEnabled(has_devices)

    # ACTIONS ----------------------------------------------------------------------

    def _on_clear_action(self) -> None:
        """Clear the scene and hide the contrast slider."""
        self._stage_viewer.clear()
        self._contrast_slider.setVisible(False)

    def _on_roi_changed(self) -> None:
        """Update the ROI manager when a new ROI is set."""
        img_w = self._mmc.getImageWidth()
        img_h = self._mmc.getImageHeight()
        if not img_w or not img_h:
            return
        px = self._mmc.getPixelSizeUm()
        self.roi_manager.update_fovs((img_w * px, img_h * px))

        if self._stage_pos_marker is not None:
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
        if self._stage_pos_marker is None:
            return
        if isinstance(sender, QActionGroup) and (action := sender.checkedAction()):
            pi = PositionIndicator(action.text())
            self._stage_pos_marker.set_rect_visible(pi.show_rect)
            self._stage_pos_marker.set_marker_visible(pi.show_marker)

    def _on_clim_range_changed(
        self, data_min: float, data_max: float, dtype_max: float
    ) -> None:
        """Update the contrast slider when the global data range expands."""
        self._contrast_slider.setVisible(True)
        self._contrast_slider.update_range(data_min, data_max, dtype_max)

    def _on_contrast_slider_changed(self, value: tuple[float, float]) -> None:
        """Apply the contrast slider values to all images."""
        self._stage_viewer.set_clims(value)

    def _on_auto_contrast_toggled(self, checked: bool) -> None:
        """Toggle auto-contrast mode."""
        if checked:
            sv = self._stage_viewer
            self._contrast_slider.autoscale(sv._global_min, sv._global_max)
            sv.set_clims((sv._global_min, sv._global_max))

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
        """Update scan settings on the ROI manager so visuals refresh."""
        overlap, mode = value
        self.roi_manager.set_scan_options(overlap, mode)

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

    def _on_sys_config_loaded(self) -> None:
        """Clear the scene and reinitialize when the system configuration is loaded."""
        self._stage_viewer.clear()
        self._contrast_slider.setVisible(False)
        self._set_stage_controller()
        self._affine_state.refresh()

        self._create_stage_pos_marker()
        self._on_roi_changed()
        self._update_actions_enabled()

        # start/stop the poller based on whether an XY stage is available
        has_xy = bool(self._mmc.getXYStageDevice())
        if has_xy and not self._stage_poller.isRunning():
            self._toolbar.poll_stage_action.setChecked(True)
            self._on_poll_stage_action(True)
            self.zoom_to_fit()
        elif not has_xy and self._stage_poller.isRunning():
            self._toolbar.poll_stage_action.setChecked(False)
            self._on_poll_stage_action(False)

    def _create_stage_pos_marker(self) -> None:
        """(Re)create the stage position marker if a camera is available."""
        w, h = self._mmc.getImageWidth(), self._mmc.getImageHeight()
        if not w or not h:
            return
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.parent = None
        self._stage_pos_marker = StagePositionMarker(
            parent=self._stage_viewer.view.scene,
            rect_width=w,
            rect_height=h,
            marker_symbol_size=min(w, h) / 10,
        )
        self._stage_pos_marker.visible = False

    def _set_stage_controller(self) -> None:
        self._stage_controller = None
        if xy_dev := self._mmc.getXYStageDevice():
            self._stage_controller = QStageMoveAccumulator.for_device(xy_dev, self._mmc)

    def _on_pixel_size_changed(self, *args: object) -> None:
        """Refresh the affine state when pixel size or affine changes."""
        self._affine_state.refresh()

    def _on_mouse_double_click(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice() or self._stage_controller is None:
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
        if self._stage_pos_marker is not None:
            self._stage_pos_marker.visible = checked
        self._poll_stage_position = checked
        if checked and self._mmc.getXYStageDevice():
            self._stage_poller.start()
        else:
            self._stop_poller()

    def _on_show_grid_action(self, checked: bool) -> None:
        """Set the show grid property based on the state of the action."""
        self._stage_viewer.set_grid_visible(checked)

    def _on_stage_position_polled(self, stage_x: float, stage_y: float) -> None:
        """Update the marker and label with the polled stage position."""
        self._stage_pos_label.setText(f"X: {stage_x:.2f} µm  Y: {stage_y:.2f} µm")

        # fast path: copy cached rotation/scale part and just update translation
        if self._stage_pos_marker is not None:
            matrix = self._affine_state.system_affine_translated(stage_x, stage_y)
            self._stage_pos_marker.apply_transform(matrix.T)

        # zoom_to_fit only if auto _auto_zoom_to_fit property is set to True.
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


_CLIM_SLIDER_SS = """
QSlider::groove:horizontal {
    height: 15px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(128, 128, 128, 0.25),
        stop:1 rgba(128, 128, 128, 0.1)
    );
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 38px;
    background: #999999;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(100, 100, 100, 0.25),
        stop:1 rgba(100, 100, 100, 0.1)
    );
}
QRangeSlider { qproperty-barColor: qlineargradient(
    x1:0, y1:0, x2:0, y2:1,
    stop:0 rgba(100, 80, 120, 0.2),
    stop:1 rgba(100, 80, 120, 0.4)
)}
SliderLabel { font-size: 10px; color: white; }
"""


class ContrastSlider(QWidget):
    """A contrast range slider with an auto-contrast toggle button."""

    valueChanged = Signal(tuple)
    """Emitted as (min, max) floats whenever the effective clim changes."""
    autoToggled = Signal(bool)
    """Emitted when the auto-contrast button is toggled."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auto: bool = True
        self._updating: bool = False

        self._slider = QLabeledRangeSlider(Qt.Orientation.Horizontal, self)
        self._slider.setStyleSheet(_CLIM_SLIDER_SS)
        self._slider.setHandleLabelPosition(
            QLabeledRangeSlider.LabelPosition.LabelsOnHandle
        )
        self._slider.setEdgeLabelMode(QLabeledRangeSlider.EdgeLabelMode.NoLabel)
        self._slider.valueChanged.connect(self._on_slider_changed)

        self._auto_btn = QPushButton("Auto", self)
        self._auto_btn.setCheckable(True)
        self._auto_btn.setChecked(True)
        self._auto_btn.setMaximumWidth(42)
        self._auto_btn.toggled.connect(self._on_auto_toggled)

        layout = QHBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._auto_btn, 0)

    @property
    def auto(self) -> bool:
        """Whether auto-contrast is enabled."""
        return self._auto

    def update_range(self, data_min: float, data_max: float, dtype_max: float) -> None:
        """Update the slider range and, if auto, the handle values."""
        self._slider.setRange(0, int(dtype_max))
        if self._auto:
            self._updating = True
            try:
                self._slider.setValue((int(data_min), int(data_max)))
            finally:
                self._updating = False

    def autoscale(self, data_min: float, data_max: float) -> None:
        """Force the slider handles to the given data range."""
        self._updating = True
        try:
            self._slider.setValue((int(data_min), int(data_max)))
        finally:
            self._updating = False

    def _on_slider_changed(self, value: tuple[int, int]) -> None:
        if not self._updating and self._auto_btn.isChecked():
            self._auto_btn.setChecked(False)
        self.valueChanged.emit((float(value[0]), float(value[1])))

    def _on_auto_toggled(self, checked: bool) -> None:
        self._auto = checked
        self.autoToggled.emit(checked)


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
    """Menu widget that exposes scan grid options (overlap + scan order)."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        opts_widget = QWidget(self)
        form = QFormLayout(opts_widget)
        form.setContentsMargins(8, 8, 8, 8)

        self._overlap_spin = QDoubleSpinBox(opts_widget)
        self._overlap_spin.setRange(-100, 100)
        self._overlap_spin.setSuffix(" %")
        form.addRow("Overlap", self._overlap_spin)

        self._mode_cbox = QEnumComboBox(self, OrderMode)
        self._mode_cbox.setCurrentEnum(OrderMode.spiral)
        form.addRow("Order", self._mode_cbox)

        action = QWidgetAction(self)
        action.setDefaultWidget(opts_widget)
        self.addAction(action)

        self._overlap_spin.valueChanged.connect(self._emit)
        self._mode_cbox.currentTextChanged.connect(self._emit)

    def value(self) -> tuple[float, useq.OrderMode]:
        """Return (overlap, order_mode)."""
        return self._overlap_spin.value(), self._mode_cbox.currentEnum()

    def _emit(self) -> None:
        self.valueChanged.emit(self.value())


@dataclass(slots=True)
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
        return R @ S

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
