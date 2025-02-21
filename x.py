import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
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

        # matrix = child.transform.matrix
        # x, y = np.round(matrix[:2, 3]).astype(int)
        # x, y = np.round(matrix[:2, 3]).astype(int)  # rounded
        # scale = np.linalg.norm(matrix[:3, 0])  # along x-axis
        # rotation = matrix[:3, :3] / scale
        # theta = np.arctan2(rotation[1, 0], rotation[0, 0])
        # theta_deg = -np.degrees(theta)

        # new_scale = scale * child.scale
        # if new_scale != current_scale:
        #     # matrix[:2, :2] = np.eye(2) * new_scale
        #     child.transform.matrix[:2, :2] = np.eye(2) * new_scale
        # print("new scale from matrix:", np.linalg.norm(matrix[:3, 0]))

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


v = V()
v.show()










    # @property
    # def pixel_size(self) -> float:
    #     """Return the pixel size. By default, the pixel size is 1.0."""
    #     return self._pixel_size

    # @pixel_size.setter
    # def pixel_size(self, value: float) -> None:
    #     """Set the pixel size."""
    #     self._pixel_size = value
    #     self._update()

        # # connect vispy events
        # self.canvas.events.draw.connect(qthrottled(self._on_draw_event))

    # def _update(self) -> None:
    #     """Update the scene based if the scale has changed."""
    #     scale = self._get_scale()
    #     if scale == self._current_scale:
    #         return
    #     self._current_scale = scale
    #     self._update_by_scale(scale)

    # def _on_draw_event(self, event: MouseEvent) -> None:
    #     """Handle the draw event.

    #     Useful for updating the scene when pan or zoom is applied.
    #     """
    #     self._update()

    # def _get_scale(self) -> int:
    #     """Return the scale based on the zoom level."""
    #     # get the transform from the camera
    #     transform = self.view.camera.transform
    #     # calculate the zoom level as the inverse of the scale factor in the transform
    #     pixel_ratio = 1 / transform.scale[0]
    #     # calculate the scale as the inverse of the zoom level
    #     scale = 1
    #     pixel_size = self._pixel_size
    #     # using *2 to not scale the image too much. Maybe find a different way?
    #     # while (pixel_ratio / scale) > (pixel_size * 2):
    #     while (pixel_ratio / scale) > (pixel_size):
    #         scale *= 2
    #     return scale

    # def _update_by_scale(self, scale: int) -> None:
    #     """Update the images in the scene based on scale and pixel size."""
    #     for child in self._get_images():
    #         child = cast(ImageData, child)
    #         matrix = child.transform.matrix
    #         print('----------------------')
    #         print(matrix)
    #         # [[   1.       0.       0.       0.   ]
    #         #  [   0.       1.       0.       0.   ]
    #         #  [   0.       0.       1.       0.   ]
    #         #  [-324.985 -120.26     0.       1.   ]]
    #         x, y = matrix[3, :2]

    #         # if the image is not within the view, skip it.
    #         # if not self._is_image_within_view(x, y, *img.shape):
    #         #     continue

    #         new_scale = scale * child.scale
    #         current_scale = np.linalg.norm(matrix[:3, 0])
    #         if new_scale != current_scale:
    #             img_scaled = child.data[::scale, ::scale]
    #             child.set_data(img_scaled)
    #             matrix[:2, :2] = np.eye(2) * new_scale
    #             # update translation
    #             w, h = img_scaled.shape
    #             matrix[3, :2] = [x + w / 2, y + h / 2]
    #             child.transform = scene.MatrixTransform(matrix=matrix)
    #             print(child.transform.matrix)