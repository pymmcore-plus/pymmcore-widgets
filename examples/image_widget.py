from typing import Optional

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from pymmcore_widgets import ExposureWidget, ImagePreview, LiveButton, SnapButton


class ImageFrame(QWidget):
    """An example widget with a snap/live button and an image preview."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.preview = ImagePreview()
        self.snap_button = SnapButton()
        self.live_button = LiveButton()
        self.exposure = ExposureWidget()

        self.setLayout(QVBoxLayout())

        buttons = QWidget()
        buttons.setLayout(QHBoxLayout())
        buttons.layout().addWidget(self.snap_button)
        buttons.layout().addWidget(self.live_button)
        buttons.layout().addWidget(self.exposure)

        self.layout().addWidget(self.preview)
        self.layout().addWidget(buttons)


if __name__ == "__main__":
    CMMCorePlus().instance().loadSystemConfiguration()
    app = QApplication([])
    frame = ImageFrame()
    frame.show()
    app.exec_()
