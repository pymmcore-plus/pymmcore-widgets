"""Example usage of the SnapButton class."""

import useq
from pymmcore_plus import CMMCorePlus

# from qtpy.QtWidgets import QApplication
from pymmcore_widgets._stage_recorder import StageRecorder
from pymmcore_widgets import MDAWidget

# app = QApplication([])

mmc = CMMCorePlus().instance()
cfg = r"c:\Users\NIC\Desktop\mm\Ti2.cfg"
mmc.loadSystemConfiguration(cfg)

rec = StageRecorder()
rec.show()

m = MDAWidget()
m.show()

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

# app.exec_()


# mmc.state(
#     devices=False,
#     image=False,
#     config_groups=False,
#     position=True,
#     cached=False
# )
