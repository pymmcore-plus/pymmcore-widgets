from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget
from pymmcore_widgets.hcs._well_calibration_widget import WellCalibrationWidget

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

app = QApplication([])

s = StageWidget("XY")
s.show()
c = WellCalibrationWidget(mmcore=mmc)


@c.calibrationChanged.connect
def _on_calibration_changed(calibrated: bool) -> None:
    if calibrated:
        print("Calibration changed! New center:", c.wellCenter())


c.setCircularWell(True)
c.show()

app.exec()
