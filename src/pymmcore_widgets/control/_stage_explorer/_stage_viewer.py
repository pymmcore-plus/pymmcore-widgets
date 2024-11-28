from typing import Optional, cast

import numpy as np
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox


class DataStore:
    """A data store for images.

    This class stores images and their stage positions in a dictionary where the keys
    are the stage positions and the values are the images.
    """

    def __init__(self) -> None:
        self.store: dict[tuple[float, float], np.ndarray] = {}

    def add_image(self, position: tuple[float, float], image: np.ndarray) -> None:
        """Add an image to the store."""
        self.store[position] = image

    def get_image(self, position: tuple[float, float]) -> np.ndarray | None:
        """Get an image from the store."""
        return self.store.get(position, None)


class StageViewer(QWidget):
    """A stage positions viewer widget.

    This widget provides a visual representation of the stage positions. The user can
    interact with the stage positions by panning and zooming the view.

    The scale of the images is automatically adjusted based on the zoom level of the
    view. A `scaleChanged` signal is emitted when the scale changes.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.

    Properties
    ----------
    image_store : DataStore
        Return the image store object that contains the images added to the scene and
        their stage positions.
    auto_reset_view : bool
        A boolean property that controls whether to automatically reset the view when an
        image is added to the scene. By default, True.
    pixel_size : float
        The pixel size in micrometers. By default, 1.0.
    flip_horizontal : bool
        A boolean property that controls whether to flip images horizontally. By
        default, False.
    flip_vertical : bool
        A boolean property that controls whether to flip images vertically. By default,
        False.
    """

    scaleChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._current_scale: int = 1

        # properties
        self._image_store: DataStore = DataStore()
        self._auto_reset_view: bool = True
        self._pixel_size: float = 1.0
        self._flip_horizontal: bool = False
        self._flip_vertical: bool = False

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast(ViewBox, self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connections
        # this is to check if the scale has changed and update the scene accordingly
        self.canvas.events.draw.connect(self._on_draw_event)

    # --------------------PUBLIC METHODS--------------------

    @property
    def image_store(self) -> DataStore:
        """Return the image store."""
        return self._image_store

    @property
    def auto_reset_view(self) -> bool:
        """Return the auto reset view property."""
        return self._auto_reset_view

    @auto_reset_view.setter
    def auto_reset_view(self, value: bool) -> None:
        """Set the auto reset view property."""
        self._auto_reset_view = value

    @property
    def pixel_size(self) -> float:
        """Return the pixel size."""
        return self._pixel_size

    @pixel_size.setter
    def pixel_size(self, value: float) -> None:
        """Set the pixel size."""
        self._pixel_size = value

    @property
    def flip_horizontal(self) -> bool:
        """Return the flip horizontally setting."""
        return self._flip_horizontal

    @flip_horizontal.setter
    def flip_horizontal(self, value: bool) -> None:
        """Set the flip horizontally setting."""
        self._flip_horizontal = value

    @property
    def flip_vertical(self) -> bool:
        """Return the flip vertically setting."""
        return self._flip_vertical

    @flip_vertical.setter
    def flip_vertical(self, value: bool) -> None:
        """Set the flip vertically setting."""
        self._flip_vertical = value

    def add_image(self, img: np.ndarray, x: float, y: float) -> None:
        """Add an image to the scene and to the image_store."""
        # flip the image if needed
        if self._flip_horizontal:
            img = np.fliplr(img)
        if self._flip_vertical:
            img = np.flipud(img)
        # move the coordinates to the center of the image
        h, w = np.array(img.shape)
        x, y = round(x - w / 2 * self.pixel_size), round(y - h / 2 * self.pixel_size)
        # store the image in the _image_store
        self._image_store.add_image((x, y), img)
        # get the current scale
        self._current_scale = scale = self.get_scale()
        # add the image to the scene with the current scale
        img = img[::scale, ::scale]
        frame = Image(img, cmap="grays", parent=self.view.scene, clim="auto")
        # keep the added image on top of the others
        order = min(child.order for child in self.view.scene.children) + -1
        frame.order = order
        frame.transform = scene.STTransform(
            scale=(scale * self.pixel_size, scale * self.pixel_size), translate=(x, y)
        )
        if self._auto_reset_view:
            self.reset_view()

    def update_by_scale(self, scale: int) -> None:
        """Update the images in the scene based on scale and pixel size."""
        for child in self.view.scene.children:
            if isinstance(child, Image):
                x, y = child.transform.translate[:2]
                img = self._image_store.get_image((x, y))
                if img is None:
                    continue
                img_scaled = img[::scale, ::scale]
                # update the image data
                child.set_data(img_scaled)
                # update the scale
                child.transform.scale = (
                    scale * self.pixel_size,
                    scale * self.pixel_size,
                )

    def get_scale(self) -> int:
        """Return the scale based on the zoom level."""
        # get the transform from the camera
        transform = self.view.camera.transform
        # calculate the zoom level as the inverse of the scale factor in the transform
        pixel_ratio = 1 / transform.scale[0]
        # Calculate the scale as the inverse of the zoom level
        scale = 1
        while pixel_ratio / scale > self.pixel_size:
            scale *= 2
        return scale

    def clear_scene(self) -> None:
        """Clear the scene."""
        self._image_store.store.clear()

        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

    def reset_view(self) -> None:
        """Recenter the view to the center of all images."""
        min_x: int | None = None
        max_x: int | None = None
        min_y: int | None = None
        max_y: int | None = None

        # get the max and min (x, y) values from _store_images
        for (x, y), img in self._image_store.store.items():
            height, width = np.array(img.shape) * self.pixel_size
            x, y = round(x), round(y)
            min_x = x if min_x is None else min(min_x, x)
            max_x = x + width if max_x is None else max(max_x, x + width)
            min_y = y if min_y is None else min(min_y, y)
            max_y = y + height if max_y is None else max(max_y, y + height)

        if min_x is None or max_x is None or min_y is None or max_y is None:
            return

        self.view.camera.set_range(x=(min_x, max_x), y=(min_y, max_y))

    # --------------------PRIVATE METHODS--------------------

    def _on_draw_event(self, event: MouseEvent) -> None:
        """Handle the draw event.

        Update the scene if the scale has changed.
        """
        scale = self.get_scale()
        if scale == self._current_scale:
            return
        self._current_scale = scale
        self.update_by_scale(scale)
        self.scaleChanged.emit(scale)
