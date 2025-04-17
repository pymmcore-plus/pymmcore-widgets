import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets import LiveButton, SnapButton, StageWidget
from pymmcore_widgets.control._stage_explorer._stage_viewer_wip import StageViewer
from pymmcore_widgets.views._image_widget import ImagePreview


class V(QWidget):
    """..."""

    def __init__(self):
        super().__init__()

        self.mmc = CMMCorePlus.instance()
        self.mmc.loadSystemConfiguration("/Users/fdrgsp/Desktop/test_config.cfg")
        self.mmc.setConfig("Channel", "Cy5")
        # mmc.setROI(0, 0, 256 * 4, 256 * 6)

        self.v = StageViewer()
        prev = ImagePreview()
        snap = SnapButton()
        live = LiveButton()
        self.rot = QDoubleSpinBox()
        self.rot.setRange(-360, 360)
        stage = StageWidget("XY")
        stage.snap_checkbox.setChecked(True)

        top = QHBoxLayout()
        top.addWidget(self.v)
        top.addWidget(prev)

        bot = QHBoxLayout()
        bot.addWidget(snap)
        bot.addWidget(stage)
        bot.addWidget(live)
        bot.addWidget(self.rot)

        layout = QVBoxLayout(self)
        layout.addLayout(top, 1)
        layout.addLayout(bot, 0)
        self.showMaximized()

        self.mmc.events.imageSnapped.connect(self._on_image_snapped)

    def _on_image_snapped(self):
        T = np.eye(4)
        affine = self.mmc.getPixelSizeAffine()
        if affine == (1, 0, 0, 0, 1, 0):
            print("USING PIXEL SIZE", self.mmc.getPixelSizeUm())
            # no pixel size affine available,
            # build one from pixel size and (optionally) rotation
            pixel_size = self.mmc.getPixelSizeUm()
            rotation_rad = np.deg2rad(self.rot.value())

            cos_ = np.cos(rotation_rad)
            sin_ = np.sin(rotation_rad)
            T[:2, :2] = np.array([[cos_, -sin_], [sin_, cos_]])
            T *= pixel_size

        else:
            print("USING AFFINE")
            # use the affine matrix as is
            T[:2, :3] = np.array(affine).reshape(2, 3)

        x_pos, y_pos = self.mmc.getXYPosition()
        x_polarity = 1
        y_polarity = 1
        T[0, 3] += x_pos * x_polarity
        T[1, 3] += y_pos * y_polarity

        # transpose matrix because vispy uses column-major order
        self.v.add_image(self.mmc.getImage(), transform=T.T)
        self.v.reset_view()


app = QApplication([])
v = V()
v.show()
app.exec()
