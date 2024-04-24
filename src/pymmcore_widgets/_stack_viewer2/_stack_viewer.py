from __future__ import annotations

from typing import Hashable
from warnings import warn

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from skimage.data import camera
from superqt import QLabeledSlider
from superqt.iconify import QIconifyIcon
from vispy import scene


def noisy_camera() -> np.ndarray:
    img = camera()
    img = img + 0.3 * img.std() * np.random.standard_normal(img.shape)
    return img


class PlayButton(QPushButton):
    PLAY_ICON = "fa6-solid:play"
    PAUSE_ICON = "fa6-solid:pause"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        icn = QIconifyIcon(self.PLAY_ICON)
        icn.addKey(self.PAUSE_ICON, state=QIconifyIcon.State.On)
        super().__init__(icn, text, parent)
        self.setCheckable(True)


class DimsSlider(QWidget):
    def __init__(self, dimension_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = dimension_name
        self._play_btn = PlayButton(dimension_name)
        self._slider = QLabeledSlider(Qt.Orientation.Horizontal, parent=self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._play_btn)
        layout.addWidget(self._slider)

    def setMaximum(self, max_val: int) -> None:
        self._slider.setMaximum(max_val)

    def setValue(self, val: int) -> None:
        self._slider.setValue(val)


class DimsSliders(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self._sliders: dict[str, DimsSlider] = {}

    def add_dimension(self, name: str) -> None:
        self._sliders[name] = slider = DimsSlider(dimension_name=name, parent=self)
        self.layout().addWidget(slider)

    def remove_dimension(self, name: str) -> None:
        try:
            slider = self._sliders.pop(name)
        except KeyError:
            warn(f"Dimension {name} not found in DimsSliders", stacklevel=2)
            return
        self.layout().removeWidget(slider)
        slider.deleteLater()


class ViewerCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._canvas = scene.SceneCanvas(parent=self, keys="interactive")
        self._camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        central_wdg: scene.Widget = self._canvas.central_widget
        self._view: scene.ViewBox = central_wdg.add_view(camera=self._camera)

        # Mapping of image key to Image visual objects
        # tbd... determine what the key should be
        # could have an image per channel,
        # but may also have multiple images per channel... in the case of tiles, etc...
        self._images: dict[Hashable, scene.visuals.Image] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas.native)

        self.add_image("key", noisy_camera())
        self.reset_view()

    def add_image(self, key: Hashable, data: np.ndarray | None = None) -> None:
        self._images[key] = img = scene.visuals.Image(
            data, cmap="grays", parent=self._view.scene
        )
        img.set_gl_state("additive", depth_test=False)

    def remove_image(self, key: Hashable) -> None:
        try:
            image = self._images.pop(key)
        except KeyError:
            warn(f"Image {key} not found in ViewerCanvas", stacklevel=2)
            return
        image.parent = None

    def reset_view(self) -> None:
        self._camera.set_range()


class StackViewer(QWidget):
    """A viewer for MDA acquisitions started by MDASequence in pymmcore-plus events."""

    def __init__(self, *, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self._canvas = ViewerCanvas()
        self._info_bar = QLabel("Info")
        self._dims_sliders = DimsSliders()
        self._dims_sliders.add_dimension("z")

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._dims_sliders)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])

    viewer = StackViewer()
    viewer.show()
    viewer.resize(600, 600)

    app.exec()
