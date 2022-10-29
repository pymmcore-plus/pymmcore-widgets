from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import CameraRoiWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

cam_roi_wdg = CameraRoiWidget()
cam_roi_wdg.show()

app.exec_()
