from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, cast

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from vispy import scene
from vispy.scene.visuals import Image

if TYPE_CHECKING:
    from collections.abc import Iterator

    from vispy.scene.widgets import ViewBox


class StageViewer(QWidget):
    """A widget to add images with a transform to a vispy canves."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast("ViewBox", self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

    # --------------------PUBLIC METHODS--------------------

    def add_image(self, img: np.ndarray, transform: np.ndarray | None = None) -> None:
        """Add an image to the scene with the given transform."""
        # normalize the transform
        if transform is None:
            transform = np.eye(4)
        else:
            transform = np.asarray(transform)
            if transform.shape != (4, 4):
                raise ValueError("Transform must be a 4x4 matrix.")
            # vispy uses a column-major order for the transform matrix
            # so we need to transpose it to get the correct order
            if np.allclose(transform[-1], (0, 0, 0, 1)):
                transform = transform.T

        # add the image to the scene with the transform
        frame = Image(img, cmap="grays", parent=self.view.scene, clim="auto")
        # keep the added image on top of the others
        frame.order = min(child.order for child in self._get_images()) - 1
        frame.transform = scene.MatrixTransform(matrix=transform)

    def clear(self) -> None:
        """Clear the scene."""
        # remove all images from the scene
        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

    def zoom_to_fit(self) -> None:
        """Recenter the view to the center of all images."""
        if not (bounds := self._get_scene_boundary()):
            return
        self.view.camera.set_range(x=bounds.x_coord, y=bounds.y_coord, margin=0)

    # --------------------PRIVATE METHODS--------------------

    def _get_images(self) -> Iterator[Image]:
        """Yield images in the scene."""
        for child in self.view.scene.children:
            if isinstance(child, Image):
                yield child

    def _get_scene_boundary(self, pixel_size: float = 1.0) -> Bounds | None:
        """Return the boundaries of the images in the scene...

        The pixel_size is used to convert the image dimensions to the scene
        coordinates.
        """
        # TODO: maybe consider also the rectangles (ROIs) in the scene
        all_corners: list[np.ndarray] = []
        for child in self._get_images():
            # get image dimensions
            w, h = child.bounds(0)[1] * pixel_size, child.bounds(1)[1] * pixel_size
            # get the (x, y) coordinates from the transform matrix
            x, y = child.transform.matrix[3, :2]
            # get the four corners of the image. NOTE: when an image is added to
            # the scene with vispy, image origin is at the bottom-left corner
            # TODO: Fix me! If we invert the coordinates in micromnager
            # (e.g. transpose X), the image origin will be at the bottom-right.
            # need to figure out what to do...
            bot_left = (x, y)
            bot_right = (x + w, y)
            top_right = (x + w, y + h)
            top_left = (x, y + h)
            corners = np.array([bot_left, bot_right, top_right, top_left])
            # transform the corners to scene coordinates
            all_corners.append(corners)

        if not all_corners:
            return None

        # combine all corners into one array and compute the bounding box
        all_corners_combined = np.vstack(all_corners)
        # create a Bounds object to store x/y coordinates and width/height
        min_x, min_y = all_corners_combined.min(axis=0)
        max_x, max_y = all_corners_combined.max(axis=0)
        return Bounds(min_x, max_x, min_y, max_y)


class Bounds(NamedTuple):
    """A named tuple to store the bounds of an image."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @property
    def x_coord(self) -> tuple[float, float]:
        """Return the x coordinates of the bounding box."""
        return self.min_x, self.max_x

    @property
    def y_coord(self) -> tuple[float, float]:
        """Return the y coordinates of the bounding box."""
        return self.min_y, self.max_y

    @property
    def width(self) -> float:
        """Return the width of the bounding box."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Return the height of the bounding box."""
        return self.max_y - self.min_y
