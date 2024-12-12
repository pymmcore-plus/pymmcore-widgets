from collections.abc import Iterator
from typing import Optional, cast

import numpy as np
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from superqt.utils import qthrottled
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox


class StageViewer(QWidget):
    """A stage positions viewer widget.

    This widget provides a visual representation of the stage positions. The user can
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.

    Properties
    ----------
    image_store : dict[tuple[float, float], np.ndarray]
        Return the image_store dictionary object where the keys are the stage positions
        and values are the images added to the scene.
    pixel_size : float
        The pixel size in micrometers. By default, 1.0.
    """

    scaleChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._current_scale: int = 1

        self._drag: bool = False

        # properties
        self._image_store: dict[tuple[float, float], np.ndarray] = {}
        self._pixel_size: float = 1.0

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast(ViewBox, self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connections (if the scale has changed, update the scene accordingly)
        self.canvas.events.draw.connect(qthrottled(self._on_draw_event))

        # self.canvas.events.mouse_move.connect(self._on_mouse_drag)
        # self.canvas.events.mouse_release.connect(self._on_mouse_release)

    # --------------------PUBLIC METHODS--------------------

    @property
    def image_store(self) -> dict[tuple[float, float], np.ndarray]:
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

        The image is also added to the `image_store` dict where the (x, y) positions are
        the keys and the images the value.

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
        # calculate the top-left corner of the image for the translation
        x, y = round(x - w / 2 * self._pixel_size), round(y - h / 2 * self._pixel_size)
        # store the image in the _image_store. NOTE: storing the translated coords and
        # not the stage coords because it will be faster and easier to get the images
        # from the _image_store when updating the scale (update_by_scale method).
        self._image_store[(x, y)] = img
        # get the current scale
        self._current_scale = scale = self.get_scale()
        # add the image to the scene with the current scale
        img = img[::scale, ::scale]
        frame = Image(img, cmap="grays", parent=self.view.scene, clim="auto")
        # keep the added image on top of the others
        frame.order = min(child.order for child in self._get_images()) - 1
        frame.transform = scene.STTransform(
            scale=(scale * self._pixel_size, scale * self._pixel_size), translate=(x, y)
        )

    def update_by_scale(self, scale: int) -> None:
        """Update the images in the scene based on scale and pixel size."""
        print()
        print("Updating by scale", scale)
        for child in self._get_images():
            x, y = child.transform.translate[:2]
            if (img := self._image_store.get((x, y))) is None:
                continue
            # if the image is not within the view, skip it. This speeds up the process
            # if not self._is_image_within_view(x, y, *img.shape):
            #     continue
            # is scale is the same, skip the update
            if scale == child.transform.scale[0] / self._pixel_size:
                continue
            img_scaled = img[::scale, ::scale]
            # update the image data
            child.set_data(img_scaled)
            # update the scale
            child.transform.scale = (scale * self._pixel_size, scale * self._pixel_size)

    def get_scale(self) -> int:
        """Return the scale based on the zoom level."""
        # get the transform from the camera
        transform = self.view.camera.transform
        # calculate the zoom level as the inverse of the scale factor in the transform
        pixel_ratio = 1 / transform.scale[0]
        # Calculate the scale as the inverse of the zoom level
        scale = 1
        # TODO: using *2 to not scale the image too much. Maybe find a better way
        while (pixel_ratio / scale) > (self._pixel_size * 2):
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
        min_x, max_x, min_y, max_y = self._get_full_boundaries()
        if any(val is None for val in (min_x, max_x, min_y, max_y)):
            return
        self.view.camera.set_range(x=(min_x, max_x), y=(min_y, max_y), margin=0)

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

    # def _on_mouse_drag(self, event: MouseEvent) -> None:
    #     """Handle the mouse drag event."""
    #     if event.is_dragging and not self._drag:
    #         self._drag = True

    # def _on_mouse_release(self, event: MouseEvent) -> None:
    #     """Handle the mouse release event."""
    #     if self._drag:
    #         self._drag = False
    #         self.update_by_scale(self._current_scale)

    def _get_images(self) -> Iterator[Image]:
        """Yield images in the scene."""
        for child in self.view.scene.children:
            if isinstance(child, Image):
                yield child

    def _get_full_boundaries(
        self,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Return the boundaries of the images in the scene."""
        min_x: float | None = None
        max_x: float | None = None
        min_y: float | None = None
        max_y: float | None = None
        # calculate the max and min values of the images in the scene.
        # NOTE: the (x, y) coords in the _image_store are the top-left corner of the
        # image.
        for (x, y), img in self._image_store.items():
            height, width = np.array(img.shape) * self._pixel_size
            x, y = round(x), round(y)
            min_x = x if min_x is None else min(min_x, x)
            max_x = x + width if max_x is None else max(max_x, x + width)
            min_y = y if min_y is None else min(min_y, y)
            max_y = y + height if max_y is None else max(max_y, y + height)
        return min_x, max_x, min_y, max_y

    # def _is_image_within_view(self, x: float, y: float, w: float, h: float) -> bool:
    #     """Return True if any vertex of the image is within the view.

    #     Note that (x, y) is the top-left corner of the image and (w, h) are the width
    #     and height of the image in pixels.
    #     """
    #     view_rect = self.view.camera.rect
    #     w, h = np.array([w, h]) * self._pixel_size
    #     vertices = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    #     return any(view_rect.contains(*vertex) for vertex in vertices)
