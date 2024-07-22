from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._well_calibration_widget import WellCalibrationWidget

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

app = QApplication([])
c = WellCalibrationWidget(mmcore=mmc)
c.setCircularWell(False)
c.show()
app.exec()
