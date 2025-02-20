# import numpy as np
# from pymmcore_plus import CMMCorePlus
# from qtpy.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

# from pymmcore_widgets import LiveButton, SnapButton, StageWidget
# from pymmcore_widgets.control._stage_explorer._stage_viewer import StageViewer
# from pymmcore_widgets.views._image_widget import ImagePreview

# app = QApplication([])

# mmc = CMMCorePlus.instance()
# mmc.loadSystemConfiguration()
# # mmc.setROI(0, 0, 256 * 4, 256 * 6)


# viewer = StageViewer()
# prev = ImagePreview()
# snap = SnapButton()
# live = LiveButton()
# stage = StageWidget("XY")
# stage.snap_checkbox.setChecked(True)


# top = QHBoxLayout()
# top.addWidget(viewer)
# top.addWidget(prev)

# bot = QHBoxLayout()
# bot.addWidget(snap)
# bot.addWidget(stage)
# bot.addWidget(live)

# wdg = QWidget()
# layout = QVBoxLayout(wdg)
# layout.addLayout(top, 1)
# layout.addLayout(bot, 0)
# wdg.showMaximized()

# HAS_RESET = [0]


# # matrix = child.transform.matrix
# # x, y = np.round(matrix[:2, 3]).astype(int)
# # x, y = np.round(matrix[:2, 3]).astype(int)  # rounded
# # scale = np.linalg.norm(matrix[:3, 0])  # along x-axis
# # rotation = matrix[:3, :3] / scale
# # theta = np.arctan2(rotation[1, 0], rotation[0, 0])
# # theta_deg = -np.degrees(theta)

# @mmc.events.imageSnapped.connect
# def _on_image_snapped():
#     T = np.eye(4)
#     affine = mmc.getPixelSizeAffine()
#     if affine == (1, 0, 0, 0, 1, 0):
#         print("USING PIXEL SIZE")
#         # no pixel size affine available,
#         # build one from pixel size and (optionally) rotation
#         pixel_size = mmc.getPixelSizeUm()
#         rotation = 0  # EXPOSE ME
#         rotation_rad = np.deg2rad(rotation)

#         cos_ = np.cos(rotation_rad)
#         sin_ = np.sin(rotation_rad)
#         T[:2, :2] = np.array([[cos_, -sin_], [sin_, cos_]])
#         T *= pixel_size

#     else:
#         print("USING AFFINE")
#         # use the affine matrix as is
#         T[:2, :3] = np.array(affine).reshape(2, 3)

#     x_pos, y_pos = mmc.getXYPosition()
#     x_polarity = 1
#     y_polarity = 1
#     T[0, 3] += x_pos * x_polarity
#     T[1, 3] += y_pos * y_polarity

#     # transpose matrix because vispy uses column-major order
#     viewer.add_image(mmc.getImage(), transform=T.T, clim=(0, 5255))

#     if not HAS_RESET[0]:
#         viewer.view.camera.set_range()
#         HAS_RESET[0] = 1


# # app.exec()
