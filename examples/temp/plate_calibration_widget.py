from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget
from pymmcore_widgets.hcs._plate_calibration_widget import PlateCalibrationWidget

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

app = QApplication([])

s = StageWidget("XY")
s.show()

wdg = PlateCalibrationWidget(mmcore=mmc)
wdg.setPlate("96-well")
wdg.show()

app.exec()
