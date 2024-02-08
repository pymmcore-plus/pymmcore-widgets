"""Example usage of the SnapButton class."""

import useq
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets import StageWidget

# from qtpy.QtWidgets import QApplication
from pymmcore_widgets._stage_recorder import StageRecorder

# app = QApplication([])

mmc = CMMCorePlus().instance()
# cfg = r"c:\Users\NIC\Desktop\mm\Ti2.cfg"
# mmc.loadSystemConfiguration(cfg)
mmc.loadSystemConfiguration()

rec = StageRecorder()
rec.show()

# m = MDAWidget()
# m.show()

s = StageWidget("XY")
s.show()

# seq = useq.MDASequence(
#     channels=["FITC"],
#     grid_plan=useq.RandomPoints(
#         num_points=10,
#         max_width=-5000,
#         max_height=5000,
#         shape="rectangle",
#         fov_width=mmc.getImageWidth(),
#         fov_height=mmc.getImageHeight(),
#         allow_overlap=False,
#     ),
# )
seq = useq.MDASequence(
    channels=["FITC"],
    grid_plan=useq.GridRowsColumns(
        rows=3,
        columns=3,
        fov_width=mmc.getImageWidth() * mmc.getPixelSizeUm(),
        fov_height=mmc.getImageHeight() * mmc.getPixelSizeUm(),
    ),
)

# app.exec_()


# mmc.state(
#     devices=False,
#     image=False,
#     config_groups=False,
#     position=True,
#     cached=False
# )
