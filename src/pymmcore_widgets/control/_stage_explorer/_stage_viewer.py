from typing import Optional, cast

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox


class DataStore:
    """A data store for images."""

    def __init__(self) -> None:
        self.store: dict[tuple[float, float], np.ndarray] = {}

    def add_image(self, position: tuple[float, float], image: np.ndarray) -> None:
        """Add an image to the store."""
        self.store[position] = image


class StageViewer(QWidget):
    """A stage positions viewer widget.

    This widget provides a visual representation of the stage positions. The user can
    interact with the stage positions by panning and zooming the view. The user can also
    move the stage to a specific position (and optiionally snap an image) by
    double-clicking on the view.

    The scale of the images is automatically adjusted based on the zoom level of the
    view.

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
    auto_reset_view : bool
        A boolean property that controls whether to automatically reset the view when an
        image is added to the scene. By default, True.
    snap_on_double_click : bool
        A boolean property that controls whether to snap an image when the user
        double-clicks on the view. By default, False.
    flip_horizontal : bool
        A boolean property that controls whether to flip images horizontally. By
        default, False.
    flip_vertical : bool
        A boolean property that controls whether to flip images vertically. By default,
        False.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmc: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._mmc = mmc or CMMCorePlus.instance()

        self._image_store: DataStore = DataStore()

        self._current_scale: int = 1

        # properties
        self._auto_reset_view: bool = True
        self._snap_on_double_click: bool = False
        self._flip_horizontal: bool = False
        self._flip_vertical: bool = False

        self._info_text: scene.Text | None = None

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast(ViewBox, self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connections to vispy events
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self.canvas.events.mouse_double_click.connect(self._move_to_clicked_position)
        # this is to check if the scale has changed and update the scene accordingly
        self.canvas.events.draw.connect(self._on_draw_event)
        # connections to core events
        self._mmc.events.pixelSizeChanged.connect(self._on_pixel_size_changed)

    # --------------------PUBLIC METHODS--------------------

    @property
    def auto_reset_view(self) -> bool:
        """Return the auto reset view property."""
        return self._auto_reset_view

    @auto_reset_view.setter
    def auto_reset_view(self, value: bool) -> None:
        """Set the auto reset view property."""
        self._auto_reset_view = value

    @property
    def snap_on_double_click(self) -> bool:
        """Return the snap on double click property."""
        return self._snap_on_double_click

    @snap_on_double_click.setter
    def snap_on_double_click(self, value: bool) -> None:
        """Set the snap on double click property."""
        self._snap_on_double_click = value

    @property
    def flip_h(self) -> bool:
        """Return the flip horizontally setting."""
        return self._flip_horizontal

    @flip_h.setter
    def flip_h(self, value: bool) -> None:
        """Set the flip horizontally setting."""
        self._flip_horizontal = value

    @property
    def flip_v(self) -> bool:
        """Return the flip vertically setting."""
        return self._flip_vertical

    @flip_v.setter
    def flip_v(self, value: bool) -> None:
        """Set the flip vertically setting."""
        self._flip_vertical = value

    def clear_scene(self) -> None:
        """Clear the scene."""
        self._image_store.store.clear()

        if self._info_text is not None:
            self._info_text.parent = None

        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

    def reset_view(self) -> None:
        """Recenter the view to the center of all images."""
        pixel_size = self._mmc.getPixelSizeUm()
        min_x: int | None = None
        max_x: int | None = None
        min_y: int | None = None
        max_y: int | None = None

        # get the max and min (x, y) values from _store_images
        for (x, y), img in self._image_store.store.items():
            height, width = np.array(img.shape) * pixel_size
            x, y = round(x), round(y)
            min_x = x if min_x is None else min(min_x, x)
            max_x = x + width if max_x is None else max(max_x, x + width)
            min_y = y if min_y is None else min(min_y, y)
            max_y = y + height if max_y is None else max(max_y, y + height)

        if min_x is None or max_x is None or min_y is None or max_y is None:
            return

        self.view.camera.set_range(x=(min_x, max_x), y=(min_y, max_y))

        self._draw_scale_info()

    # --------------------PRIVATE METHODS--------------------

    def _on_pixel_size_changed(self, value: float) -> None:
        """Clear the scene when the pixel size changes."""
        # should this be a different behavior?
        self.clear_scene()

    def _move_to_clicked_position(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        if not self._mmc.getXYStageDevice():
            return
        x, y, _, _ = self.view.camera.transform.imap(event.pos)
        self._mmc.setXYPosition(x, y)
        if self._snap_on_double_click:
            self._mmc.snapImage()

    def _on_draw_event(self, event: MouseEvent) -> None:
        """Handle the draw event.

        Update the scene if the scale has changed.
        """
        scale = self._get_scale()
        if scale == self._current_scale:
            return
        self._current_scale = scale
        self._update_scene_by_scale(scale)
        self._draw_scale_info()

    def _get_scale(self) -> int:
        """Return the scale based on the zoom level."""
        # get the transform from the camera
        transform = self.view.camera.transform
        # calculate the zoom level as the inverse of the scale factor in the transform
        pixel_ratio = 1 / transform.scale[0]
        # Calculate the scale as the inverse of the zoom level
        scale = 1
        while pixel_ratio / scale > self._mmc.getPixelSizeUm():
            scale *= 2
        return scale

    def _on_image_snapped(self) -> None:
        """Add the snapped image to the scene."""
        # get the snapped image
        img = self._mmc.getImage()
        # get the current stage position
        x, y = self._mmc.getXYPosition()
        # move the coordinates to the center of the image
        self._add_image(img, x, y)

    def _on_frame_ready(self, image: np.ndarray, event: useq.MDAEvent) -> None:
        """Add the image to the scene when frameReady event is emitted."""
        x = event.x_pos if event.x_pos is not None else self._mmc.getXPosition()
        y = event.y_pos if event.y_pos is not None else self._mmc.getYPosition()
        self._add_image(image, x, y)

    def _add_image(self, img: np.ndarray, x: float, y: float) -> None:
        """Add an image to the scene and to the _image_store."""
        # flip the image if needed
        if self._flip_horizontal:
            img = np.fliplr(img)
        if self._flip_vertical:
            img = np.flipud(img)
        # move the coordinates to the center of the image
        h, w = np.array(img.shape)
        pixel_size = self._mmc.getPixelSizeUm()
        x, y = round(x - w / 2 * pixel_size), round(y - h / 2 * pixel_size)
        # store the image in the _image_store
        self._image_store.add_image((x, y), img)
        # get the current scale
        self._current_scale = scale = self._get_scale()
        # add the image to the scene with the current scale
        img = img[::scale, ::scale]
        frame = Image(img, cmap="grays", parent=self.view.scene, clim="auto")
        # keep the added image on top of the others
        order = min(child.order for child in self.view.scene.children) + -1
        frame.order = order
        frame.transform = scene.STTransform(
            scale=(scale * pixel_size, scale * pixel_size), translate=(x, y)
        )
        if self._auto_reset_view:
            self.reset_view()
        else:
            self._draw_scale_info()

    def _update_scene_by_scale(self, scale: int) -> None:
        """Update the images in the scene based on the scale."""
        pixel_size = self._mmc.getPixelSizeUm()
        for child in self.view.scene.children:
            if isinstance(child, Image):
                x, y = child.transform.translate[:2]
                img = self._image_store.store[(x, y)]
                img_scaled = img[::scale, ::scale]
                # update the image data
                child.set_data(img_scaled)
                # update the scale
                child.transform.scale = (scale * pixel_size, scale * pixel_size)

    def _draw_scale_info(self) -> None:
        """Update scale text on the top-right corner."""
        # remove the previous text if it exists
        if self._info_text is not None:
            self._info_text.parent = None

        # create the text visual only once
        self._info_text = scene.Text(
            f"scale: {self._get_scale()}",
            color="white",
            parent=self.canvas.scene,
            anchor_x="right",
            anchor_y="top",
        )
        # move the text to the top-right corner
        self._info_text.transform = scene.STTransform(
            translate=(self.canvas.size[0] - 10, 30)
        )
