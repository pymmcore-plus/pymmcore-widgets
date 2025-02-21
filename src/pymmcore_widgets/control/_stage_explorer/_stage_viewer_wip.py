from collections.abc import Iterator
from typing import Any, Optional, cast

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from superqt.utils import qthrottled
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox


class ImageData(Image):
    """A subclass of vispy's Image visual.

    A data property has been added to easy access the image data.
    A scale property has been added to store the original scale of the image.
    """

    def __init__(self, data: np.ndarray, *args: Any, **kwargs: Any) -> None:
        super().__init__(data, *args, **kwargs)
        # unfreeze the visual to allow setting the scale
        self.unfreeze()
        self._imagedata = data
        self._scale: float = 1

    @property
    def data(self) -> np.ndarray:
        """Return the image data."""
        return self._imagedata

    @property
    def scale(self) -> float:
        """Return the scale of the image."""
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        """Set the scale of the image."""
        self._scale = value


class StageViewer(QWidget):
    """A stage positions viewer widget.

    This widget provides a visual representation of the stage positions.
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.

    Properties
    ----------
    image_store : dict[tuple[float, float], np.ndarray]
        Return the image_store dictionary object where the keys are the stage positions
        and values are the images added to the scene.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast(ViewBox, self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1)

        # pixel size property
        self._pixel_size: float = 1.0

        # to store the displayed images scale
        self._current_scale: float = 1

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connect vispy events
        self.canvas.events.draw.connect(qthrottled(self._on_draw_event))

    @property
    def pixel_size(self) -> float:
        """Return the pixel size. By default, the pixel size is 1.0."""
        return self._pixel_size

    @pixel_size.setter
    def pixel_size(self, value: float) -> None:
        """Set the pixel size."""
        self._pixel_size = value
        self._update()

    # --------------------PUBLIC METHODS--------------------

    def add_image(self, img: np.ndarray, transform: np.ndarray) -> None:
        """Add an image to the scene with the given transform."""
        frame = ImageData(img, cmap="grays", parent=self.view.scene, clim="auto")
        frame.scale = self._pixel_size
        # keep the added image on top of the others
        frame.order = min(child.order for child in self._get_images()) - 1
        # add the image to the scene with the transform
        frame.transform = scene.MatrixTransform(matrix=transform)

    def clear_scene(self) -> None:
        """Clear the scene."""
        # remove all images from the scene
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

    def _update(self) -> None:
        """Update the scene based if the scale has changed."""
        scale = self._get_scale()
        if scale == self._current_scale:
            return
        self._current_scale = scale
        self._update_by_scale(scale)

    def _on_draw_event(self, event: MouseEvent) -> None:
        """Handle the draw event.

        Useful for updating the scene when pan or zoom is applied.
        """
        self._update()

    def _get_scale(self) -> int:
        """Return the scale based on the zoom level."""
        # get the transform from the camera
        transform = self.view.camera.transform
        # calculate the zoom level as the inverse of the scale factor in the transform
        pixel_ratio = 1 / transform.scale[0]
        # calculate the scale as the inverse of the zoom level
        scale = 1
        pixel_size = self._pixel_size
        # using *2 to not scale the image too much. Maybe find a different way?
        # while (pixel_ratio / scale) > (pixel_size * 2):
        while (pixel_ratio / scale) > (pixel_size):
            scale *= 2
        return scale

    def _update_by_scale(self, scale: int) -> None:
        """Update the images in the scene based on scale and pixel size."""
        for child in self._get_images():
            child = cast(ImageData, child)
            matrix = child.transform.matrix

            # if the image is not within the view, skip it.
            # x, y = matrix[:2, 3]
            # if not self._is_image_within_view(x, y, *img.shape):
            #     continue

            new_scale = scale / child.scale
            current_scale = np.linalg.norm(matrix[:3, 0])
            if new_scale != current_scale:
                img_scaled = child.data[::scale, ::scale]
                print(img_scaled.shape)
                child.set_data(img_scaled)
                child.transform.matrix[:2, :2] = np.eye(2) * current_scale / scale
                print(child.transform.matrix)

    def _get_images(self) -> Iterator[Image]:
        """Yield images in the scene."""
        for child in self.view.scene.children:
            if isinstance(child, Image):
                yield child

    def _get_full_boundaries(
        self,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Return the boundaries of the images in the scene...

        as (min_x, max_x, min_y, max_y).
        """
        # TODO: maybe consider also the rectangles (ROIs) in the scene
        all_corners: list[np.ndarray] = []
        for child in self._get_images():
            # get image dimensions
            w, h = child.bounds(0)[1], child.bounds(1)[1]
            # get the (x, y) coordinates from the transform matrix
            x, y = child.transform.matrix[:2, 3]
            # define the four corners of the image (bottom-left origin by vispy default)
            corners = np.array([[x, y], [x + w, y], [x, y + h], [x + w, y + h]])
            # transform the corners to scene coordinates
            all_corners.append(child.transform.map(corners)[:, :2])

        if not all_corners:
            return None, None, None, None

        # combine all corners into one array and compute the bounding box
        all_corners_combined = np.vstack(all_corners)
        min_x, min_y = all_corners_combined.min(axis=0)
        max_x, max_y = all_corners_combined.max(axis=0)
        return min_x, max_x, min_y, max_y
