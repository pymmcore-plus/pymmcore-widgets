from collections.abc import Iterator
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

    def clear(self) -> None:
        """Clear the store."""
        self.store.clear()

    def add_image(self, position: tuple[float, float], image: np.ndarray) -> None:
        """Add an image to the store."""
        self.store[position] = image

    def get_image(self, position: tuple[float, float]) -> np.ndarray | None:
        """Get an image from the store."""
        return self.store.get(position, None)

    def __iter__(self) -> Iterator[tuple[tuple[float, float], np.ndarray]]:
        return iter(self.store.items())


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
    pixel_size : float
        The pixel size in micrometers. By default, 1.0.
    """

    scaleChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._current_scale: int = 1

        # properties
        self._image_store: DataStore = DataStore()
        self._pixel_size: float = 1.0

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast(ViewBox, self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connections (if the scale has changed, update the scene accordingly)
        self.canvas.events.draw.connect(self._on_draw_event)

    # --------------------PUBLIC METHODS--------------------

    @property
    def image_store(self) -> DataStore:
        """Return the image store."""
        return self._image_store

    @property
    def pixel_size(self) -> float:
        """Return the pixel size."""
        return self._pixel_size

    @pixel_size.setter
    def pixel_size(self, value: float) -> None:
        """Set the pixel size."""
        self._pixel_size = value

    def add_image(self, img: np.ndarray, x: float, y: float) -> None:
        """Add an image to the scene.

        The image is also added to the `image_store` DataStore which is a dictionary
        that uses the (x, y) positions as key and the images as value.

        Parameters
        ----------
        img : np.ndarray
            The image to add to the scene.
        x : float
            The x position of the image.
        y : float
            The y position of the image.
        """
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
        frame.order = min(child.order for child in self._get_images()) - 1
        frame.transform = scene.STTransform(
            scale=(scale * self.pixel_size, scale * self.pixel_size), translate=(x, y)
        )

    def update_by_scale(self, scale: int) -> None:
        """Update the images in the scene based on scale and pixel size."""
        for child in self._get_images():
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
        self._image_store.clear()

        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

    def reset_view(self) -> None:
        """Recenter the view to the center of all images."""
        min_x, max_x, min_y, max_y = self._get_boundaries()
        if any(val is None for val in (min_x, max_x, min_y, max_y)):
            return
        self.view.camera.set_range(x=(min_x, max_x), y=(min_y, max_y))

    # --------------------PRIVATE METHODS--------------------

    def _get_boundaries(
        self,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Return the boundaries of the images in the scene."""
        min_x: float | None = None
        max_x: float | None = None
        min_y: float | None = None
        max_y: float | None = None
        # get the max and min (x, y) values from _store_images
        for (x, y), img in self._image_store:
            height, width = np.array(img.shape) * self.pixel_size
            x, y = round(x), round(y)
            min_x = x if min_x is None else min(min_x, x)
            max_x = x + width if max_x is None else max(max_x, x + width)
            min_y = y if min_y is None else min(min_y, y)
            max_y = y + height if max_y is None else max(max_y, y + height)
        return min_x, max_x, min_y, max_y

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

    def _get_images(self) -> list[Image]:
        """Return a list of images in the scene."""
        return [child for child in self.view.scene.children if isinstance(child, Image)]
