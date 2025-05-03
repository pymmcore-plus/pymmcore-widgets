from __future__ import annotations

from typing import TYPE_CHECKING, cast

import cmap
import numpy as np
import vispy
import vispy.scene
import vispy.visuals
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout, QWidget
from vispy import scene
from vispy.scene.visuals import Image

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from vispy.scene.widgets import ViewBox

    class VisualNode(vispy.scene.Node, vispy.visuals.Visual): ...


class StageViewer(QWidget):
    """A widget to add images with a transform to a vispy canves."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._clims: tuple[float, float] | None = None
        self._cmap: cmap.Colormap = cmap.Colormap("gray")

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast("ViewBox", self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

    # --------------------PUBLIC METHODS--------------------

    def set_clims(self, clim: tuple[float, float] | None) -> None:
        """Set the color limits of the images in the scene."""
        self._clims = clim
        for child in self._get_images():
            child.clim = "auto" if clim is None else clim

    def set_colormap(self, colormap: cmap.ColormapLike) -> None:
        """Set the colormap of the images in the scene."""
        self._cmap = cmap.Colormap(colormap)
        for child in self._get_images():
            child.cmap = self._cmap.to_vispy()

    def global_autoscale(self, *, ignore_min: float = 0, ignore_max: float = 0) -> None:
        """Set the color limits of all images in the scene to the global min and max."""
        if not (visuals := list(self._get_images())):
            return

        # NOTE: if this function is to be called more often, we could retain a running
        # min and max for each image and only update min and max when adding an image.
        mi, ma = np.percentile(
            np.concatenate([child._data.flatten() for child in visuals]),
            (ignore_min, 100 - ignore_max),
        )
        self.set_clims((mi, ma))

    def add_image(self, img: np.ndarray, transform: np.ndarray | None = None) -> None:
        """Add an image to the scene with the given transform.

        Parameters
        ----------
        img : np.ndarray
            The image to add to the scene. It should be a (Y, X) or (Y, X, 3) array.
        transform : np.ndarray | None
            The transform to apply to the image. It should be a 4x4 matrix.
            If None, the image will be added with the identity transform.
            The transformation is indented to be calculated elsewhere (in higher level
            widgets) based on, e.g., the stage position, pixel size, configuration
            affine, etc.  This is a relatively low-level, direct function.
        """
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
        frame = Image(
            img,
            cmap=self._cmap.to_vispy(),
            parent=self.view.scene,
            clim="auto" if self._clims is None else self._clims,
        )
        # keep the added image on top of the others
        frame.order = min(child.order for child in self._get_images()) - 1
        frame.transform = scene.MatrixTransform(matrix=transform)
        if len(list(self._get_images())) == 1:
            # if this is the first image, set the camera to fit it
            self.zoom_to_fit()

    def clear(self) -> None:
        """Clear the scene."""
        # remove all images from the scene
        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

    def zoom_to_fit(self, *, margin: float = 0.05) -> None:
        """Recenter the view to the center of all images.

        Parameters
        ----------
        margin : float
            Extra margin to add between the images and the edge of the view.
            This is a percentage of the view size. Default is 0.05 (5%).
        """
        if not (visuals := self._get_images()):
            return
        x_bounds, y_bounds, *_ = get_vispy_scene_bounds(visuals)
        self.view.camera.set_range(x=x_bounds, y=y_bounds, margin=margin)

    # --------------------PRIVATE METHODS--------------------

    def _get_images(self) -> Iterator[Image]:
        """Yield images in the scene."""
        for child in self.view.scene.children:
            if isinstance(child, Image):
                yield child


def get_vispy_scene_bounds(
    visuals: Iterable[VisualNode],
) -> tuple[list[float], list[float], list[float]]:
    """Get the bounding box for `visuals` in world coordinates."""
    # tracks: [xmin, xmax], [ymin, ymax], [zmin, zmax]
    bounds = np.array([[np.inf, -np.inf], [np.inf, -np.inf], [np.inf, -np.inf]])

    for obj in visuals:
        (x_min, x_max), (y_min, y_max) = obj.bounds(0), obj.bounds(1)
        local_bounds = np.array([[x_min, y_min, 0, 1], [x_max, y_max, 0, 1]])

        # Map local bounds to world coordinates
        transform = obj.node_transform(obj.scene_node)
        world_bounds = transform.map(local_bounds)

        # Convert from homogeneous to 3D coordinates
        world_bounds = world_bounds[:, :3] / world_bounds[:, 3, np.newaxis]

        # Update world bounds
        bounds[:, 0] = np.minimum(bounds[:, 0], world_bounds.min(axis=0))
        bounds[:, 1] = np.maximum(bounds[:, 1], world_bounds.max(axis=0))

    # replace inf values with 0 ... better than -inf
    bounds = np.where(np.isinf(bounds), 0, bounds)

    return tuple(bounds.tolist())
