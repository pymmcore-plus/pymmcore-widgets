import contextlib
from collections.abc import Iterator
from typing import Any, Optional, cast

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from vispy import scene
from vispy.app.canvas import KeyEvent, MouseEvent
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox
from vispy.util.keys import Key


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

        # to handle the drawing of rois
        self._rois: list[scene.visuals.Rectangle] = []
        self._roi_start_pos: tuple[float, float] | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connect vispy events
        self.canvas.events.mouse_press.connect(self._on_mouse_press)
        self.canvas.events.mouse_move.connect(self._on_mouse_move)
        self.canvas.events.mouse_release.connect(self._on_mouse_release)
        self.canvas.events.key_press.connect(self._on_key_press)

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

    def rois(self) -> list[tuple[float, float, float, float]]:
        """Return the list of ROIs in the scene as (top, bottom, left, right) coords."""
        tblr: list[tuple[float, float, float, float]] = []
        for rect in self._rois:
            x, y = rect.center
            w, h = rect.width, rect.height
            tblr.append(
                (
                    y + h / 2,  # top
                    y - h / 2,  # bottom
                    x - w / 2,  # left
                    x + w / 2,  # right
                )
            )
        return tblr

    # --------------------PRIVATE METHODS--------------------

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
            x, y = child.transform.matrix[3, :2]
            # define the four corners of the image (bottom-left origin by vispy default)
            corners = np.array([[x, y], [x + w, y], [x, y + h], [x + w, y + h]])
            # transform the corners to scene coordinates
            all_corners.append(corners)

        if not all_corners:
            return None, None, None, None

        # combine all corners into one array and compute the bounding box
        all_corners_combined = np.vstack(all_corners)
        min_x, min_y = all_corners_combined.min(axis=0)
        max_x, max_y = all_corners_combined.max(axis=0)
        return min_x, max_x, min_y, max_y

    # --------------------ROI--------------------

    def _tform(self) -> scene.transforms.BaseTransform:
        """Return the transform from canvas to scene."""
        return self._rois[-1].transforms.get_transform("canvas", "scene")

    def _on_mouse_press(self, event: MouseEvent) -> None:
        """Handle the mouse press event."""
        if (Key("Alt").name in event.modifiers) and event.button == 1:
            self.view.camera.interactive = False
            rect = self._create_rect()
            self._rois.append(rect)
            rect.visible = True
            canvas_pos = (event.pos[0], event.pos[1])
            world_pos = self._tform().map(canvas_pos)[:2]
            self._roi_start_pos = world_pos

    def _on_mouse_move(self, event: MouseEvent) -> None:
        """Handle the mouse drag event."""
        if (
            Key("Alt").name in event.modifiers
            and self._roi_start_pos is not None
            and event.button == 1
        ):
            canvas_pos = (event.pos[0], event.pos[1])
            world_pos = self._tform().map(canvas_pos)[:2]
            self._update_rectangle(world_pos)
            return

    def _on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        if (
            Key("Alt").name in event.modifiers
            and self._roi_start_pos is not None
            and event.button == 1
        ):
            self._roi_start_pos = None
            self.view.camera.interactive = True
            # self.rectChanged.emit(self._rects)

    def _on_key_press(self, event: KeyEvent) -> None:
        """Delete the last rectangle added to the scene when pressing Cmd/Ctrl + Z."""
        key: Key = event.key
        modifiers: tuple[Key, ...] = event.modifiers
        if (
            key == Key("Z")
            and (Key("Meta") in modifiers or Key("Control") in modifiers)
            and self._rois
        ):
            self._rois.pop(-1).parent = None
            # self.rectChanged.emit(self._rects)

    def _create_rect(self) -> scene.visuals.Rectangle:
        """Create a new rectangle visual."""
        new_rect = scene.visuals.Rectangle(
            center=[0, 0],
            width=1,
            height=1,
            color=None,
            border_color="yellow",
            border_width=2,
            parent=self.view.scene,
        )
        new_rect.set_gl_state(depth_test=False)
        return new_rect

    def _update_rectangle(self, end: tuple[float, float]) -> None:
        """Update the rectangle visual with correct coordinates."""
        if self._roi_start_pos is None:
            return
        with contextlib.suppress(Exception):
            x0, y0 = self._roi_start_pos
            x1, y1 = end
            rect = self._rois[-1]
            rect.center = (x0 + x1) / 2, (y0 + y1) / 2
            width, height = abs(x0 - x1), abs(y0 - y1)
            rect.width = width
            rect.height = height
