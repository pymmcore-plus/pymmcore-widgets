import sys
from itertools import cycle
from typing import Any

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

shape = (512, 512)
images = cycle((np.random.rand(100, *shape) * 255).astype(np.uint8))


def np2qimg(data: np.ndarray) -> QImage:
    if np.ndim(data) == 2:
        data = data[..., None]
    elif np.ndim(data) != 3:
        raise ValueError("data must be 2D or 3D")
    if data.shape[-1] not in (1, 2, 3, 4):
        raise ValueError(
            "Last dimension must contain one (scalar/gray), two (gray+alpha), "
            "three (R,G,B), or four (R,G,B,A) channels"
        )
    h, w, nc = data.shape
    np_dtype = data.dtype
    hasAlpha = nc in (2, 4)
    isRGB = nc in (3, 4)
    if np_dtype == np.uint8:
        if hasAlpha:
            fmt = QImage.Format.Format_RGBA8888
        elif isRGB:
            fmt = QImage.Format.Format_RGB888
        else:
            fmt = QImage.Format.Format_Grayscale8
    elif np_dtype == np.uint16:
        if hasAlpha:
            fmt = QImage.Format.Format_RGBA64
        elif isRGB:
            fmt = QImage.Format.Format_RGB16
        else:
            fmt = QImage.Format.Format_Grayscale16
    elif np_dtype == np.float32:
        if hasAlpha:
            fmt = QImage.Format.Format_RGBA32FPx4
        elif isRGB:
            fmt = QImage.Format.Format_RGBA16FPx4
        else:
            dmin = data.min()
            data = ((data - dmin) / (data.max() - dmin) * 255).astype(np.uint8)
            fmt = QImage.Format.Format_Grayscale8
    qimage = QImage(data, w, h, fmt)
    return qimage


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
        self.add_image()

        # Use a timer to update the image
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_image)
        self.timer.start(10)

    def add_image(self) -> None:
        self.image_data = next(images)
        qimage = np2qimg(self.image_data)

        # Convert QImage to QPixmap and add it to the scene using QGraphicsPixmapItem
        self.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(qimage))
        self.scene.addItem(self.pixmap_item)

    def resizeEvent(self, event: Any) -> None:
        self.fitInView()

    def fitInView(self) -> None:
        # Scale view to fit the pixmap preserving the aspect ratio
        if not self.pixmap_item.pixmap().isNull():
            self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def update_image(self) -> None:
        # Update the image with new random data
        self.image_data = next(images)
        qimage = np2qimg(self.image_data)
        self.pixmap_item.setPixmap(QPixmap.fromImage(qimage))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageWindow()
    window.show()
    sys.exit(app.exec())
