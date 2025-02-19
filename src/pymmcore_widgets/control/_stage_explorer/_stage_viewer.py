import contextlib
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
from vispy.geometry import Rect
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox
from vispy.util.keys import Key


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

        self._roi: bool = False
        self._rect_start_pos: tuple[float, float] | None = None

        # properties
        self._image_store: dict[float, dict[tuple[float, float], np.ndarray]] = {}
        self._pixel_size: float = 1.0

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast(ViewBox, self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1)

        self._rect = scene.visuals.Rectangle(
            center=[0, 0],
            width=1,
            height=1,
            color=None,
            border_color="yellow",
            border_width=2,
            parent=self.view.scene,
        )
        self._rect.set_gl_state(depth_test=False)
        self._rect.visible = False

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connections (if the scale has changed, update the scene accordingly)
        self.canvas.events.draw.connect(qthrottled(self._on_draw_event))
        self.canvas.events.mouse_press.connect(self._on_mouse_press)
        self.canvas.events.mouse_move.connect(self._on_mouse_move)
        self.canvas.events.mouse_release.connect(self._on_mouse_release)

    # --------------------PUBLIC METHODS--------------------

    @property
    # def image_store(self) -> dict[tuple[float, float], np.ndarray]:
    def image_store(self) -> dict[float, dict[tuple[float, float], np.ndarray]]:
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

    @property
    def roi(self) -> bool:
        """Return True if the ROI is active."""
        return self._roi

    @roi.setter
    def roi(self, value: bool) -> None:
        """Set the ROI."""
        self._roi = value

    @property
    def rect(self) -> scene.visuals.Rectangle:
        """Return the rectangle visual."""
        return self._rect

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
        # in vispy, when you add an image and translate it, the (x, y) translation
        # coordinates represent the bottom-left corner of the image. For us is better
        # to have the (x, y) coordinates represent the center of the image. So we need
        # to adjust the coordinates and move the image to the left and bottom by half of
        # the width and height of the image. We also have to considet the pixel size.
        h, w = np.array(img.shape)
        x, y = round(x - w / 2 * self._pixel_size), round(y - h / 2 * self._pixel_size)
        # store the image in the _image_store. NOTE: once the image is added to the view
        # the (x, y) coords represent the bottom-left corner of the vispy Image.
        if self.pixel_size not in self._image_store:
            self._image_store[self.pixel_size] = {}
        self._image_store[self.pixel_size][(x, y)] = img
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
        for child in self._get_images():
            x, y = child.transform.translate[:2]
            if (img := self._image_store.get(self._pixel_size, {}).get((x, y))) is None:
                continue
            # if the image is not within the view, skip it.
            if not self._is_image_within_view(x, y, *img.shape):
                continue
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

        # reset the rectangle visual
        self._rect.visible = False
        self._rect.center = (0, 0)
        self._rect.width = 1
        self._rectheight = 1

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

    def _tform(self) -> scene.transforms.BaseTransform:
        """Return the transform from canvas to scene."""
        return self._rect.transforms.get_transform("canvas", "scene")

    def _on_mouse_press(self, event: MouseEvent) -> None:
        """Handle the mouse press event."""
        if (self._roi or Key("Alt").name in event.modifiers) and event.button == 1:
            self.view.camera.interactive = False
            self._rect.visible = True
            canvas_pos = (event.pos[0], event.pos[1])
            world_pos = self._tform().map(canvas_pos)[:2]
            self._rect_start_pos = world_pos

    def _on_mouse_move(self, event: MouseEvent) -> None:
        """Handle the mouse drag event."""
        if self._roi or (
            Key("Alt").name in event.modifiers
            and self._rect_start_pos is not None
            and event.button == 1
        ):
            canvas_pos = (event.pos[0], event.pos[1])
            world_pos = self._tform().map(canvas_pos)[:2]
            self.update_rectangle(world_pos)
            return
        if event.is_dragging and not self._drag:
            self._drag = True
        if self._drag:
            self.update_by_scale(self._current_scale)

    def update_rectangle(self, end: tuple[float, float]) -> None:
        """Update the rectangle visual with correct coordinates."""
        if self._rect_start_pos is None:
            return
        with contextlib.suppress(Exception):
            x0, y0 = self._rect_start_pos
            x1, y1 = end
            self._rect.center = (x0 + x1) / 2, (y0 + y1) / 2
            width, height = abs(x0 - x1), abs(y0 - y1)
            self._rect.width = width
            self._rect.height = height

    def _on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        if self._roi or (
            Key("Alt").name in event.modifiers
            and self._rect_start_pos is not None
            and event.button == 1
        ):
            self._rect_start_pos = None
            self.view.camera.interactive = True
            return
        if self._drag:
            self._drag = False
            self.update_by_scale(self._current_scale)

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
        # NOTE: the (x, y) coords in the _image_store are the bottom-left corner of the
        # vispy Image.
        # first get the biggest pixel size key in the image store and use it to get the
        # current image store so we get the borders of the images with the biggest pixel
        # size and thus the biggest images.
        max_px_size = max(self._image_store.keys(), default=1)
        current_image_store = self._image_store.get(max_px_size, {})
        for (x, y), img in current_image_store.items():
            height, width = np.array(img.shape) * self._pixel_size
            min_x = x if min_x is None else min(min_x, x)  # left
            max_x = x + width if max_x is None else max(max_x, x + width)  # right
            min_y = y if min_y is None else min(min_y, y)  # bottom
            max_y = y + height if max_y is None else max(max_y, y + height)  # top
        return min_x, max_x, min_y, max_y

    def _is_image_within_view(self, x: float, y: float, w: float, h: float) -> bool:
        """
        Return True if any part of the image is within the view.

        Note that (x, y) is the bottom-left corner of the image and (w, h) are the width
        and height of the image in micrometers.
        """
        # scale image dimensions by pixel size
        w, h = np.array([w, h]) * self._pixel_size
        # create a Rect for the image
        image_rect = Rect(x, y, w, h)
        # get the view Rect
        view_rect = cast(Rect, self.view.camera.rect)
        # check for overlap
        return not (
            image_rect.left > view_rect.right
            or image_rect.right < view_rect.left
            or image_rect.top < view_rect.bottom
            or image_rect.bottom > view_rect.top
        )
