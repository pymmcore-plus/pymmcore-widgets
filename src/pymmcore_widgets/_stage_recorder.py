from typing import Any, Optional, cast

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QAction,
    QMenu,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from skimage.transform import resize
from superqt.fonticon import icon
from useq import MDAEvent
from vispy import scene
from vispy.color import Color
from vispy.scene.visuals import Image, Rectangle
from vispy.visuals.transforms import STTransform

SCALE_FACTOR = 3
GRAY = "#666"
GREEN = Color("#0ba322")
RESET = "Auto Reset View"
SNAP = "Auto Snap on double click"
FLIP_H = "Flip Image Horizontally"
FLIP_V = "Flip Image Vertically"
POLL = "Poll XY Stage Movements"
POLL_INTERVAL = 250


class StageRecorder(QWidget):
    """A stage positions viewer widget."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Recorder")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._visited_positions: list[tuple[float, float]] = []
        self._fov_max: tuple[float, float] = (0, 0)
        self._auto_reset: bool = True
        self._snap: bool = False
        self._flip_h: bool = False
        self._flip_v: bool = False

        self._poll_timer = QTimer()
        self._poll_timer.setInterval(POLL_INTERVAL)
        self._poll_timer.timeout.connect(self._on_stage_position_changed)

        # canvas and view
        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)

        # add to main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        # toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # reset view action
        self._act_reset_view = QAction(
            icon(MDI6.home_outline, color=GRAY), "Reset View", self
        )
        self._act_reset_view.triggered.connect(self.reset_view)
        toolbar.addAction(self._act_reset_view)

        # clear action
        self._act_clear = QAction(
            icon(MDI6.close_box_outline, color=GRAY), "Clear View", self
        )
        self._act_clear.triggered.connect(self.clear_view)
        toolbar.addAction(self._act_clear)

        # settings button and context menu
        # create settings button
        self._settings_btn = QToolButton()
        self._settings_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._settings_btn.setToolTip("Settings Menu")
        self._settings_btn.setIcon(icon(MDI6.cog_outline, color=GRAY))
        toolbar.addWidget(self._settings_btn)
        # create context menu
        menu = QMenu(self)
        # connect the menu to the button click
        self._settings_btn.setMenu(menu)
        # create actions for checkboxes
        self._auto_reset_act = QAction(RESET, self, checkable=True, checked=True)
        self._auto_snap_act = QAction(SNAP, self, checkable=True)
        self._flip_h_act = QAction(FLIP_H, self, checkable=True)
        self._flip_v_act = QAction(FLIP_V, self, checkable=True)
        self._poll_act = QAction(POLL, self, checkable=True)
        # add actions to the menu
        menu.addAction(self._auto_reset_act)
        menu.addAction(self._auto_snap_act)
        menu.addAction(self._flip_h_act)
        menu.addAction(self._flip_v_act)
        menu.addAction(self._poll_act)
        # add actions to the checkboxes
        self._auto_reset_act.triggered.connect(self._on_setting_checked)
        self._auto_snap_act.triggered.connect(self._on_setting_checked)
        self._flip_h_act.triggered.connect(self._on_setting_checked)
        self._flip_v_act.triggered.connect(self._on_setting_checked)
        self._poll_act.triggered.connect(self._on_setting_checked)

        # add to main layout
        main_layout.addWidget(toolbar)
        main_layout.addWidget(self.canvas.native)

        # connect signals
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self.canvas.events.mouse_double_click.connect(self._on_mouse_double_click)

        self._on_sys_config_loaded()

    # __________________________PUBLIC METHODS__________________________

    @property
    def auto_reset(self) -> bool:
        """Return the auto reset setting."""
        return self._auto_reset

    @auto_reset.setter
    def auto_reset(self, value: bool) -> None:
        """Set the auto reset setting."""
        self._auto_reset = value
        self._auto_reset_act.setChecked(value)

    @property
    def auto_snap(self) -> bool:
        """Return the auto snap setting."""
        return self._snap

    @auto_snap.setter
    def auto_snap(self, value: bool) -> None:
        """Set the auto snap setting."""
        self._snap = value
        self._auto_snap_act.setChecked(value)

    @property
    def flip_h(self) -> bool:
        """Return the flip horizontally setting."""
        return self._flip_h

    @flip_h.setter
    def flip_h(self, value: bool) -> None:
        """Set the flip horizontally setting."""
        self._flip_h = value
        self._flip_h_act.setChecked(value)

    @property
    def flip_v(self) -> bool:
        """Return the flip vertically setting."""
        return self._flip_v

    @flip_v.setter
    def flip_v(self, value: bool) -> None:
        """Set the flip vertically setting."""
        self._flip_v = value
        self._flip_v_act.setChecked(value)

    @property
    def poll_xy_stage(self) -> bool:
        """Return the poll setting."""
        return bool(self._poll_timer.isActive())

    @poll_xy_stage.setter
    def poll_xy_stage(self, value: bool) -> None:
        """Set the poll setting."""
        self._toggle_poll_timer(value)
        self._poll_act.setChecked(value)

    def clear_view(self) -> None:
        """Clear the scene and the visited positions."""
        # clear visited position list
        self._visited_positions.clear()
        # clear scene
        self._delete_images()
        self._delete_preview()
        # reset view
        if self._auto_reset:
            self.reset_view()

    def reset_view(self) -> None:
        """Set the camera range to fit all the visited positions."""
        preview = self._get_preview_rect()

        if not self._visited_positions and not preview:
            self.view.camera.set_range()
            return

        # if only the preview is present, set the range to the preview position
        if not self._visited_positions and preview is not None:
            # get preview center position
            (x, y) = preview.center
            self.view.camera.set_range(
                x=(x - (preview.width / 2), x + (preview.width / 2)),
                y=(y - (preview.height / 2), y + (preview.height / 2)),
            )
            return

        # get the edges from all the visited positions
        (x_min, x_max), (y_min, y_max) = self._get_edges_from_visited_points()

        # if there is a preview rectangle, also consider its positio to set the range
        if preview is not None:
            # get preview position
            x, y = preview.center
            # compare the preview position with the edges
            x_min = min(x_min, x - (preview.width / 2))
            x_max = max(x_max, x + (preview.width / 2))
            y_min = min(y_min, y - (preview.height / 2))
            y_max = max(y_max, y + (preview.height / 2))

        self.view.camera.set_range(x=(x_min, x_max), y=(y_min, y_max))

    def value(self) -> list[tuple[float, float]]:
        """Return the visited positions."""
        # return a copy of the list considering the SCALE_FACTOR
        return [
            (x * SCALE_FACTOR, y * SCALE_FACTOR) for x, y in self._visited_positions
        ]

    # __________________________PRIVATE METHODS__________________________

    def _on_sys_config_loaded(self) -> None:
        self._auto_snap_act.setEnabled(bool(self._mmc.getCameraDevice()))
        self._poll_act.setEnabled(bool(self._mmc.getXYStageDevice()))
        self._poll_act.setChecked(bool(self._mmc.getXYStageDevice()))
        self._toggle_poll_timer(bool(self._mmc.getXYStageDevice()))

    def _on_property_changed(self, device: str, property: str, value: str) -> None:
        if device != "Core" or property not in {"Camera", "XYStage"}:
            return

        # update the settings checkboxes if Camera or XYStage
        self._on_sys_config_loaded()

    def _on_setting_checked(self, checked: bool) -> None:
        """Handle the settings checkboxes."""
        sender = cast(QAction, self.sender()).text()
        if sender == RESET:
            self._auto_reset = checked
        elif sender == SNAP:
            self._snap = checked
        elif sender == FLIP_H:
            self._flip_h = checked
        elif sender == FLIP_V:
            self._flip_v = checked
        elif sender == POLL:
            self._toggle_poll_timer(checked)

    def _on_mouse_double_click(self, event: Any) -> None:
        """Move the stage to the mouse position.

        If the autosnap checkbox is checked, also snap an image.
        """
        # if the mda is running, return
        if self._mmc.mda.is_running():
            return

        # if is the first position the scene is used, do not move the stage and just
        # snap an image
        if self._visited_positions:
            # Get mouse position in camera coordinates
            x, y, _, _ = self.view.camera.transform.imap(event.pos)
            self._mmc.setXYPosition(x * SCALE_FACTOR, y * SCALE_FACTOR)

        if not self._mmc.getCameraDevice():
            self._auto_snap_act.setChecked(False)
            self._snap = False
            return

        if self._snap and not self._mmc.isSequenceRunning():
            self._mmc.snapImage()

    def _toggle_poll_timer(self, on: bool) -> None:
        if not on:
            self._delete_preview()

        if not self._mmc.getXYStageDevice():
            self._poll_timer.stop()
            self._poll_act.setChecked(False)
            return

        self._poll_timer.start() if on else self._poll_timer.stop()

    def _on_stage_position_changed(self) -> None:
        """Update the scene with the current position."""
        if self._mmc.mda.is_running():
            return
        self._update_preview()

    def _update_preview(self) -> None:
        """Update the preview rectangle position."""
        # get current position
        x, y = self._mmc.getXPosition(), self._mmc.getYPosition()
        # delete the previous preview rectangle
        self._delete_preview()
        # draw the fov around the position
        self._draw_fov(x / SCALE_FACTOR, y / SCALE_FACTOR)
        if self._auto_reset:
            self.reset_view()

    def _draw_fov(self, x: float, y: float) -> None:
        """Draw a the fov position on the canvas."""
        if not self._mmc.getCameraDevice():
            return
        # draw the position as a fov around the (x, y) position coordinates
        w, h = self._get_image_size()
        fov = Rectangle(
            center=(x, y), width=w, height=h, border_color=GREEN, border_width=3
        )
        self.view.add(fov)

    def _delete_preview(self) -> None:
        """Delete all images from the scene."""
        for child in reversed(self.view.scene.children):
            if isinstance(child, Rectangle):
                child.parent = None

    def _get_preview_rect(self) -> Rectangle | None:  # sourcery skip: use-next
        """Get the preview rectangle from the scene."""
        for child in self.view.scene.children:
            if isinstance(child, Rectangle):
                return child
        return None

    def _set_max_fov(self) -> None:
        """Set the max fov based on the image size.

        The max size is stored in self._fov_max so that if during the session the image
        size changes, the max fov will be updated and the view will be properly reset.
        """
        img_width, img_height = self._get_image_size()

        current_width_max, current_height_max = self._fov_max
        self._fov_max = (
            max(img_width, current_width_max),
            max(img_height, current_height_max),
        )

    def _get_edges_from_visited_points(
        self,
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Get the edges of the visited positions."""
        x = [pos[0] for pos in self._visited_positions]
        y = [pos[1] for pos in self._visited_positions]
        x_min, x_max = (min(x), max(x))
        y_min, y_max = (min(y), max(y))
        # consider the fov size
        return (
            (x_min - self._fov_max[0], x_max + self._fov_max[0]),
            (y_min - self._fov_max[1], y_max + self._fov_max[1]),
        )

    def _get_image_size(self) -> tuple[float, float]:
        """Get the image size in pixel from the camera."""
        img_width = self._mmc.getImageWidth() * self._mmc.getPixelSizeUm()
        img_height = self._mmc.getImageHeight() * self._mmc.getPixelSizeUm()
        return img_width / SCALE_FACTOR, img_height / SCALE_FACTOR

    def _on_frame_ready(self, image: np.ndarray, event: MDAEvent) -> None:
        x = event.x_pos if event.x_pos is not None else self._mmc.getXPosition()
        y = event.y_pos if event.y_pos is not None else self._mmc.getYPosition()
        self._update_scene_with_image(image, x / SCALE_FACTOR, y / SCALE_FACTOR)

    def _on_image_snapped(self) -> None:
        """Update the scene with the current position."""
        # delete the previous preview rectangle if any
        self._delete_preview()
        # if the mda is running, we will use the frameReady event to update the scene
        if self._mmc.mda.is_running():
            return

        # get snapped image
        image = self._mmc.getImage()
        # get current position
        x, y = self._mmc.getXPosition(), self._mmc.getYPosition()
        # update the scene with the image
        self._update_scene_with_image(image, x / SCALE_FACTOR, y / SCALE_FACTOR)

    def _update_scene_with_image(self, image: np.ndarray, x: float, y: float) -> None:
        # return if the position is already visited
        if (x, y) in self._visited_positions:
            return

        # add the position to the visited positions list
        self._visited_positions.append((x, y))

        # set the max fov depending on the image size
        self._set_max_fov()

        # add the image to the scene
        self._add_image(image, x, y)

    def _add_image(self, image: np.ndarray, x: float, y: float) -> None:
        """Add an image to the scene."""
        width, height = self._get_image_size()

        # scale
        scaled = resize(image, (height, width))
        # flip horizontally
        if self._flip_h:
            scaled = np.fliplr(scaled)
        # flip vertically
        if self._flip_v:
            scaled = np.flipud(scaled)

        scaled_8bit = (scaled / scaled.max()) * 255
        scaled_8bit = np.uint8(scaled_8bit)

        clim = (scaled_8bit.min(), scaled_8bit.max())

        frame = Image(scaled_8bit, cmap="grays", parent=self.view.scene, clim=clim)

        # set the position of the image so that the center of the image is at the given
        # (x, y) position
        x -= width / 2
        y -= height / 2
        frame.transform = STTransform(translate=(x, y))

        if self._auto_reset:
            self.reset_view()

    def _delete_images(self) -> None:
        """Delete all images from the scene."""
        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None
