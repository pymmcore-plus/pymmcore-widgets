from collections.abc import Iterable
from typing import Optional, cast

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox
from vispy.visuals.transforms import STTransform


class DataStore:
    """A data store for images."""

    def __init__(self):
        self.store: dict[tuple[float, float], np.ndarray] = {}

    def add_image(self, position: tuple[float, float], image: np.ndarray):
        """Add an image to the store."""
        self.store[position] = image

    def request_bounds(
        self, scale: int, bounds: tuple[float, float]
    ) -> Iterable[tuple[tuple[float, float], np.ndarray]]:
        """Request images within the bounds."""
        ...


class StageExplorer(QWidget):
    """A stage positions viewer widget."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmc: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._mmc = mmc or CMMCorePlus.instance()

        self._image_store: DataStore = DataStore()

        self._current_scale: int = 1

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = cast(ViewBox, self.canvas.central_widget.add_view())
        self.view.camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        self._info_text: scene.Text | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.canvas.native)

        # connections
        self._mmc.events.imageSnapped.connect(self._on_image_snapped)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self.canvas.events.mouse_double_click.connect(self._move_to_clicked_position)
        # this is to check if the scale has changed and update the scene accordingly
        self.canvas.events.draw.connect(self._on_draw_event)

    # --------------------PUBLIC METHODS--------------------

    def reset_widget(self) -> None:
        """Reset the widget and the variables."""
        self.clear_scene()
        self._image_store = DataStore()
        self._current_scale = 1
        self._info_text = None

    def clear_scene(self) -> None:
        """Clear the scene."""
        if self._info_text is not None:
            self._info_text.parent = None

        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

    # --------------------PRIVATE METHODS--------------------

    def _move_to_clicked_position(self, event: MouseEvent) -> None:
        """Move the stage to the clicked position."""
        x, y, _, _ = self.view.camera.transform.imap(event.pos)
        self._mmc.setXYPosition(x, y)

    def _on_draw_event(self, event: MouseEvent | None) -> None:
        """Handle the draw event.

        Update the scene based on the scale.
        """
        scale = self._get_scale()
        if scale != self._current_scale:
            self._current_scale = scale
            self._update_scene_by_scale(scale)
            self._draw_scale_info()

    def _get_scale(self) -> int:
        """Return the scale based on the zoom level."""
        # this just maps the camera to the scene.
        coords = self.view.camera.transform.imap([[0, 0], [1, 0]])
        pixel_ratio = coords[1][0] - coords[0][0]
        # get breakpoints for zoom levels of pixel_ratio of powers of 2
        scale = 1
        while pixel_ratio / scale > 1:
            scale *= 2
        return scale

    def _reset_view(self) -> None:
        # TODO: fix this, it is not correctly centering the view
        min_x, max_x = None, None
        min_y, max_y = None, None

        for child in self.view.scene.children:
            if isinstance(child, Image):
                x, y = child.transform.translate[:2]
                height, width = child.size

                x, y = round(x), round(y)  # Normalize coordinates

                # Update bounds
                min_x = x if min_x is None else min(min_x, x)
                max_x = x + width if max_x is None else max(max_x, x + width)
                min_y = y if min_y is None else min(min_y, y)
                max_y = y + height if max_y is None else max(max_y, y + height)

        if (
            min_x is not None
            and max_x is not None
            and min_y is not None
            and max_y is not None
        ):
            self.view.camera.set_range(
                x=(round(min_x), round(max_x)),
                y=(round(min_y), round(max_y)),
            )

        self._draw_scale_info()

    def _on_image_snapped(self) -> None:
        """Add the snapped image to the scene."""
        # get the snapped image
        img = self._mmc.getImage()
        # get the current stage position
        x, y = self._mmc.getXYPosition()
        # move the coordinates to the center of the image
        self._add_image(img, x, y)

    def _add_image(self, img: np.ndarray, x: float, y: float) -> None:
        h, w = img.shape
        x, y = round(x - w / 2), round(y - h / 2)
        # store the image in the _image_store
        self._image_store.add_image((x, y), img)
        # get the current scale
        scale = self._get_scale()
        # add the image to the scene with the current scale
        img = img[::scale, ::scale]
        frame = Image(img, cmap="grays", parent=self.view.scene)
        frame.transform = scene.STTransform(scale=(scale, scale), translate=(x, y))
        # TODO: make self._reset_view() optional
        self._reset_view()
        self._draw_scale_info()

    def _on_frame_ready(self, image: np.ndarray, event: useq.MDAEvent) -> None:
        x = event.x_pos if event.x_pos is not None else self._mmc.getXPosition()
        y = event.y_pos if event.y_pos is not None else self._mmc.getYPosition()
        self._add_image(image, x, y)

    def _update_scene_by_scale(self, scale: int) -> None:
        """Update the images in the scene based on the scale."""
        for child in self.view.scene.children:
            if isinstance(child, Image):
                x, y = child.transform.translate[:2]
                img = self._image_store.store[(x, y)]
                img_scaled = img[::scale, ::scale]
                child.set_data(img_scaled)
                child.transform.scale = (scale, scale)

    def _draw_scale_info(self) -> None:
        """Update scale text on the top-right corner."""
        # remove the previous text if it exists
        if self._info_text is not None:
            self._info_text.parent = None

        # txt = f"Scale: {self._current_scale}"
        txt = f"Scale: {self._get_scale()}"

        # create the text visual only once
        self._info_text = scene.Text(
            txt,
            color="white",
            parent=self.canvas.scene,
            anchor_x="right",
            anchor_y="top",
        )
        # move the text to the top-right corner
        self._info_text.transform = STTransform(
            translate=(self.canvas.size[0] - 10, 30)
        )


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication, QPushButton

    from pymmcore_widgets import StageWidget

    app = QApplication([])

    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()
    # set camera size to 2048x2048
    mmc.setProperty("Camera", "OnCameraCCDXSize", 2048)
    mmc.setProperty("Camera", "OnCameraCCDYSize", 2048)
    mmc.setExposure(100)
    # TODO: fix for pixel size =! 1
    # mmc.setProperty("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    # print(mmc.getPixelSizeUm())

    exp = StageExplorer()
    exp.show()

    stage = StageWidget("XY")
    stage.setStep(512)
    stage.snap_checkbox.setChecked(True)
    stage._invert_y.setChecked(True)
    stage.show()

    btn = QPushButton("Reset")
    btn.clicked.connect(exp.reset_widget)
    btn.show()

    app.exec()
