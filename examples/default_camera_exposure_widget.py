from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import DefaultCameraExposureWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

exp_wdg = DefaultCameraExposureWidget()
exp_wdg.show()

app.exec_()
