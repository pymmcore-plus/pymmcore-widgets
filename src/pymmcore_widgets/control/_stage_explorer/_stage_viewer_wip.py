from collections.abc import Iterator
from typing import Any, Optional, cast

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from vispy import scene
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox


class ImageData(Image):
    """A subclass of vispy's Image visual.

    A data property has been added to easy access the image data.
    """

    def __init__(self, data: np.ndarray, *args: Any, **kwargs: Any) -> None:
        super().__init__(data, *args, **kwargs)
        # unfreeze the visual to allow setting the scale
        self.unfreeze()
        self._imagedata = data

    @property
    def data(self) -> np.ndarray:
        """Return the image data."""
        return self._imagedata


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

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

    # --------------------PUBLIC METHODS--------------------

    def add_image(self, img: np.ndarray, transform: np.ndarray) -> None:
        """Add an image to the scene with the given transform."""
        frame = ImageData(img, cmap="grays", parent=self.view.scene, clim="auto")
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

    def _get_images(self) -> Iterator[Image]:
        """Yield images in the scene."""
        for child in self.view.scene.children:
            if isinstance(child, Image):
                yield child

    def _get_full_boundaries(
        self, pixel_size: float = 1.0
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Return the boundaries of the images in the scene...

        as (min_x, max_x, min_y, max_y).

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
            # define the four corners of the image
            # note: we use a coords system where (0, 0) is the origin, going
            # up and right is positive and going down and left is negative.
            # When an image is added to the scene with vispy, its origin is at
            # the bottom-right corner.
            corners = np.array(
                [
                    [x, y], # bottom-right
                    [x - w, y], # bottom-left
                    [x - w, y + h], # top-left
                    [x, y + h], # top-right
                ]
            )
            # transform the corners to scene coordinates
            all_corners.append(corners)

        if not all_corners:
            return None, None, None, None

        # combine all corners into one array and compute the bounding box
        all_corners_combined = np.vstack(all_corners)
        min_x, min_y = all_corners_combined.min(axis=0)
        max_x, max_y = all_corners_combined.max(axis=0)
        return min_x, max_x, min_y, max_y
