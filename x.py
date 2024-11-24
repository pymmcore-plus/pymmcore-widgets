from collections.abc import Iterable
from typing import Optional, cast

import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from skimage.transform import resize
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image
from vispy.scene.widgets import ViewBox
from vispy.visuals.transforms import STTransform

ZOOM_TO_SCALE = [
    # (zoom, scale)
    (1, 1),  # zoom >= 1 -> scale = 1
    (0.25, 2),  # zoom >= 0.25 -> scale = 2
    (0.0625, 8),  # zoom >= 0.0625 -> scale = 8
    # (1, 1),  # zoom >= 1 -> scale = 1
    # (0.5, 2),  # 1 > zoom >= 0.5 -> scale = 2
    # (0.25, 4),  # 0.5 > zoom >= 0.25 -> scale = 4
    # (0.125, 8),  # 0.25 > zoom >= 0.125 -> scale = 8
    # (0.0625, 16),  # 0.125 > zoom >= 0.0625 -> scale = 16
]


class DataStore:
    """A data store for images."""

    def __init__(self):
        self.store: dict[int, dict[tuple[float, float], np.ndarray]] = {}

    def add_image(self, scale: int, position: tuple[float, float], image: np.ndarray):
        """Add an image to the store."""
        if scale not in self.store:
            self.store[scale] = {}
        self.store[scale][position] = image

    def scale_images(self, scale: int) -> None:
        """Scale the store."""
        if scale in self.store:
            return
        if scale == 1:
            return
        self.store[scale] = {}
        for (x, y), img in self.store[1].items():
            height, width = img.shape
            new_shape = (height // scale, width // scale)
            new_img = resize(img, new_shape, anti_aliasing=True, preserve_range=True)
            self.store[scale][(round(x / scale, 2), round(y / scale, 2))] = new_img

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

        self.canvas.events.mouse_wheel.connect(self._on_mouse_wheel)

    def reset(self):
        """Reset the widget and the variables."""
        self.clear_scene()
        self._image_store = DataStore()
        self._current_scale = 1
        self._info_text = None
        self._reset_view()

    def clear_scene(self) -> None:
        """Clear the scene."""
        if self._info_text is not None:
            self._info_text.parent = None

        for child in reversed(self.view.scene.children):
            if isinstance(child, Image):
                child.parent = None

        self._reset_view()

    def get_zoom(self) -> float:
        """Return the zoom level."""
        return self.view.camera.transform.scale[0] / self._current_scale

    def _draw_zoom_and_scale_info(self) -> None:
        """Update zoom and scale text on the top-right corner."""
        # remove the previous text if it exists
        if self._info_text is not None:
            self._info_text.parent = None

        zoom = self.get_zoom()
        txt = f"Zoom: {zoom:.2f}, Scale: {self._current_scale}"

        # create the text visual only once
        self._info_text = scene.Text(
            txt,
            color="white",
            parent=self.canvas.scene,
            anchor_x="right",
            anchor_y="top",
        )
        self._info_text.transform = STTransform(
            translate=(self.canvas.size[0] - 10, 30)
        )

    def _on_mouse_wheel(self, event: MouseEvent | None) -> None:
        """On mouse wheel events."""
        # if the zoom level has changed, update the scene accordingly (redraw images)
        scale = self._get_scale_from_zoom()
        if scale != self._current_scale:
            self._current_scale = scale
            self._update_scene_by_scale(scale)

        self._draw_zoom_and_scale_info()

    def _reset_view(self) -> None:
        min_x, max_x = None, None
        min_y, max_y = None, None

        for child in self.view.scene.children:
            if isinstance(child, Image):
                # Extract only the x and y components of the translation
                x, y = child.transform.translate[:2]
                height, width = child.size
                # Update bounds
                min_x = x if min_x is None else min(min_x, x)
                max_x = x + width if max_x is None else max(max_x, x + width)
                min_y = y if min_y is None else min(min_y, y)
                max_y = y + height if max_y is None else max(max_y, y + height)

        # Ensure bounds are valid before setting range
        if (
            min_x is not None
            and max_x is not None
            and min_y is not None
            and max_y is not None
        ):
            self.view.camera.set_range(x=(min_x, max_x), y=(min_y, max_y))

    def _on_image_snapped(self) -> None:
        x, y = self._mmc.getXYPosition()

        x, y = round(x, 2), round(y, 2)

        img = self._mmc.getImage()

        # always store the image at scale 1
        self._image_store.add_image(1, (x, y), img)

        # if the current scale is not 1, store the image at the current scale
        if self._current_scale != 1:
            h, w = np.array(img.shape) // self._current_scale
            img = resize(img, (h, w), anti_aliasing=True, preserve_range=True)
            x, y = round(x / self._current_scale, 2), round(y / self._current_scale, 2)
            self._image_store.add_image(self._current_scale, (x, y), img)

        # draw the image
        frame = Image(img, cmap="grays", parent=self.view.scene)

        # translate the image to the correct position
        imheight, imwidth = img.shape
        x, y = x - imwidth / 2, y - imheight / 2
        frame.transform = STTransform(translate=(x, y))
        self._reset_view()

        # if the zoom level has changed, update the scene accordingly (redraw images)
        scale = self._get_scale_from_zoom()
        if scale != self._current_scale:
            self._current_scale = scale
            self._update_scene_by_scale(scale)
            self._reset_view()

        self._draw_zoom_and_scale_info()

    def _get_scale_from_zoom(self) -> int:
        """Return the scale based on the zoom level."""
        zoom = self.get_zoom()
        for threshold, scale in ZOOM_TO_SCALE:
            if zoom >= threshold:
                return scale
        return 32

    def _update_scene_by_scale(self, scale: int) -> None:
        """Redraw all the images in the scene based on the scale."""
        self.clear_scene()

        if scale not in self._image_store.store:
            self._image_store.scale_images(scale)

        for (x, y), img in self._image_store.store[scale].items():
            frame = Image(img, cmap="grays", parent=self.view.scene)
            height, width = img.shape
            x -= width / 2
            y -= height / 2
            frame.transform = STTransform(translate=(x, y))


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication, QPushButton

    from pymmcore_widgets import StageWidget

    app = QApplication([])

    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()

    exp = StageExplorer()
    exp.show()

    stage = StageWidget("XY")
    stage.setStep(512)
    stage.snap_checkbox.setChecked(True)
    stage._invert_y.setChecked(True)
    stage.show()

    btn = QPushButton("Reset")
    btn.clicked.connect(exp.reset)
    btn.show()

    app.exec()
