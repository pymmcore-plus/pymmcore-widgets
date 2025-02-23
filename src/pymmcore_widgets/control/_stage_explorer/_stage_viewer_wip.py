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

from ._rois import ROIRectangle


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
        self._rois: list[ROIRectangle] = []

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
            top_left, bottom_right = rect.bounding_box()
            tblr.append((top_left[1], bottom_right[1], top_left[0], bottom_right[0]))
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

    def _active_roi(self) -> ROIRectangle | None:
        """Return the next active ROI."""
        return next((roi for roi in self._rois if roi.selected()), None)

    def _on_mouse_press(self, event: MouseEvent) -> None:
        """Handle the mouse press event."""
        canvas_pos = (event.pos[0], event.pos[1])

        if self._active_roi() is not None:
            self.view.camera.interactive = False

        # create a new roi only if the Alt key is pressed
        # TODO: add button to activate/deactivate the ROI creation as well as to delete
        # all the ROIs
        elif Key("Alt").name in event.modifiers and event.button == 1:
            self.view.camera.interactive = False
            # create the ROI rectangle for the first time
            roi = self._create_roi(canvas_pos)
            self._rois.append(roi)

    def _create_roi(self, canvas_pos: tuple[float, float]) -> ROIRectangle:
        """Create a new ROI rectangle and connect its events."""
        roi = ROIRectangle(self.view.scene)
        roi.connect(self.canvas)
        world_pos = roi._tform().map(canvas_pos)[:2]
        roi.set_selected(True)
        roi.set_visible(True)
        roi.set_anchor(world_pos)
        roi.set_bounding_box(world_pos, world_pos)
        return roi

    def _on_mouse_move(self, event: MouseEvent) -> None:
        """Update the cursor shape when hovering over the ROIs."""
        if (roi := self._active_roi()) is not None:
            cursor = roi.get_cursor(event)
            self.canvas.native.setCursor(cursor)
        else:
            self.canvas.native.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        self.view.camera.interactive = True

    def _on_key_press(self, event: KeyEvent) -> None:
        """Delete the last ROI added to the scene when pressing Cmd/Ctrl + Z."""
        key: Key = event.key
        modifiers: tuple[Key, ...] = event.modifiers
        if (
            key == Key("Z")
            and (Key("Meta") in modifiers or Key("Control") in modifiers)
            and self._rois
        ):
            roi = self._rois.pop(-1)
            roi.remove()
            with contextlib.suppress(Exception):
                roi.disconnect(self.canvas)
