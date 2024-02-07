"""Example usage of the SnapButton class."""

from pymmcore_plus import CMMCorePlus

# from qtpy.QtWidgets import QApplication
from pymmcore_widgets._stage_recorder import StageRecorder

# app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

rec = StageRecorder()
rec.show()

# app.exec_()
