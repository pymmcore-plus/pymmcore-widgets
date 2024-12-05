from typing import Optional

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QDockWidget, QMainWindow, QVBoxLayout, QWidget
from vispy import scene

IMG = np.random.rand(100, 100)


class VispyWidget(QWidget):
    """A custom widget containing a VisPy canvas."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VisPy Dock Widget")

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas.native)

    def add_image(self, image):
        """Add an image to the VisPy canvas."""
        image = scene.visuals.Image(image, parent=self.view.scene)

    def reset_view(self):
        """Reset the camera view."""
        self.view.camera.set_range()


class MainWindow(QMainWindow):
    """Main window containing a dock widget with the VisPy canvas."""

    def __init__(self):
        super().__init__()
        self.setCentralWidget(QWidget())
        vispy_widget = VispyWidget(parent=self)
        dock = QDockWidget("VisPy Dock", self)
        dock.setWidget(vispy_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        # add an image
        vispy_widget.add_image(IMG)
        vispy_widget.reset_view()


if __name__ == "__main__":
    qt_app = QApplication([])
    window = MainWindow()
    window.show()
    qt_app.exec()
