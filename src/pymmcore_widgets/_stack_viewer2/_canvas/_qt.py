from __future__ import annotations

import sys
from typing import Any, Callable

import cmap
import numpy as np
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QImage, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

_FORMATS: dict[tuple[np.dtype, int], QImage.Format] = {
    (np.dtype(np.uint8), 1): QImage.Format.Format_Grayscale8,
    (np.dtype(np.uint8), 3): QImage.Format.Format_RGB888,
    (np.dtype(np.uint8), 4): QImage.Format.Format_RGBA8888,
    (np.dtype(np.uint16), 1): QImage.Format.Format_Grayscale16,
    (np.dtype(np.uint16), 3): QImage.Format.Format_RGB16,
    (np.dtype(np.uint16), 4): QImage.Format.Format_RGBA64,
    (np.dtype(np.float32), 1): QImage.Format.Format_Grayscale8,
    (np.dtype(np.float32), 3): QImage.Format.Format_RGBA16FPx4,
    (np.dtype(np.float32), 4): QImage.Format.Format_RGBA32FPx4,
}


def _normalize255(
    array: np.ndarray,
    normalize: tuple[bool, bool] | bool,
    clip: tuple[int, int] = (0, 255),
) -> np.ndarray:
    # by default, we do not want to clip in-place
    # (the input array should not be modified):
    clip_target = None

    if normalize:
        if normalize is True:
            if array.dtype == bool:
                normalize = (False, True)
            else:
                normalize = array.min(), array.max()
            if clip == (0, 255):
                clip = None
        elif np.isscalar(normalize):
            normalize = (0, normalize)

        nmin, nmax = normalize

        if nmin:
            array = array - nmin
            clip_target = array

        if nmax != nmin:
            if array.dtype == bool:
                scale = 255.0
            else:
                scale = 255.0 / (nmax - nmin)

            if scale != 1.0:
                array = array * scale
                clip_target = array

    if clip:
        low, high = clip
        array = np.clip(array, low, high, clip_target)

    return array


def np2qimg(data: np.ndarray) -> QImage:
    if np.ndim(data) == 2:
        data = data[..., None]
    elif np.ndim(data) != 3:
        raise ValueError("data must be 2D or 3D")
    if data.shape[-1] not in (1, 3, 4):
        raise ValueError(
            "Last dimension must contain one (scalar/gray), "
            "three (R,G,B), or four (R,G,B,A) channels"
        )
    h, w, nc = data.shape

    fmt = _FORMATS.get((data.dtype, data.shape[-1]))
    if fmt is None:
        raise ValueError(f"Unsupported data type {data.dtype} with {nc} channels")

    if data.dtype == np.float32 and data.shape[-1] == 1:
        dmin = data.min()
        data = ((data - dmin) / (data.max() - dmin) * 255).astype(np.uint8)
        fmt = QImage.Format.Format_Grayscale8
    print(data.shape, w, h, fmt, data.min(), data.max())
    qimage = QImage(data, w, h, fmt)
    return qimage


class QtImageHandle:
    def __init__(self, item: QGraphicsPixmapItem, data: np.ndarray) -> None:
        self._data = data
        self._item = item

    @property
    def data(self) -> np.ndarray:
        return self._data

    @data.setter
    def data(self, data: np.ndarray) -> None:
        self._data = data.squeeze()
        self._item.setPixmap(QPixmap.fromImage(np2qimg(self._data)))

    @property
    def visible(self) -> bool:
        return self._item.isVisible()

    @visible.setter
    def visible(self, visible: bool) -> None:
        self._item.setVisible(visible)

    @property
    def clim(self) -> Any:
        return (0, 255)

    @clim.setter
    def clim(self, clims: tuple[float, float]) -> None:
        pass

    @property
    def cmap(self) -> cmap.Colormap:
        return cmap.Colormap("viridis")

    @cmap.setter
    def cmap(self, cmap: cmap.Colormap) -> None:
        pass

    def remove(self) -> None:
        """Remove the image from the scene."""
        if scene := self._item.scene():
            scene.removeItem(self._item)


class QtViewerCanvas(QWidget):
    """Vispy-based viewer for data.

    All vispy-specific code is encapsulated in this class (and non-vispy canvases
    could be swapped in if needed as long as they implement the same interface).
    """

    def __init__(self, set_info: Callable[[str], None]) -> None:
        super().__init__()

        # Create a QGraphicsScene which holds the graphics items
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene, self)
        self.view.setBackgroundBrush(Qt.GlobalColor.black)

        # make baground of this widget black
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def qwidget(self) -> QWidget:
        return self

    def refresh(self) -> None:
        """Refresh the canvas."""
        self.update()

    def add_image(
        self, data: np.ndarray | None = None, cmap: cmap.Colormap | None = None
    ) -> QtImageHandle:
        """Add a new Image node to the scene."""
        item = QGraphicsPixmapItem(QPixmap.fromImage(np2qimg(data)))
        self.scene.addItem(item)
        return QtImageHandle(item, data)

    def set_range(
        self,
        x: tuple[float, float] | None = None,
        y: tuple[float, float] | None = None,
        margin: float | None = 0.01,
    ) -> None:
        """Update the range of the PanZoomCamera.

        When called with no arguments, the range is set to the full extent of the data.
        """


class ImageWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        # Create a QGraphicsScene which holds the graphics items
        self.scene = QGraphicsScene()

        # Create a QGraphicsView which provides a widget for displaying the contents of a QGraphicsScene
        self.view = QGraphicsView(self.scene, self)
        self.view.setBackgroundBrush(Qt.GlobalColor.black)

        # make baground of this widget black
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        # Create a QImage from random data
        self.image_data = next(images)
        qimage = QImage(self.image_data, *shape, QImage.Format.Format_RGB888)

        # Convert QImage to QPixmap and add it to the scene using QGraphicsPixmapItem
        self.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(qimage))
        self.scene.addItem(self.pixmap_item)

        # Use a timer to update the image
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_image)
        self.timer.start(10)

    def resizeEvent(self, event: Any) -> None:
        self.fitInView()

    def fitInView(self) -> None:
        # Scale view to fit the pixmap preserving the aspect ratio
        if not self.pixmap_item.pixmap().isNull():
            self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def update_image(self) -> None:
        # Update the image with new random data
        self.image_data = next(images)
        qimage = QImage(self.image_data, *shape, QImage.Format.Format_RGB888)
        self.pixmap_item.setPixmap(QPixmap.fromImage(qimage))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageWindow()
    window.show()
    sys.exit(app.exec())
