import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget
from pymmcore_widgets.hcs._plate_calibration_widget import PlateCalibrationWidget

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

app = QApplication([])

s = StageWidget("XY")
s.show()

plan = useq.WellPlatePlan(
    plate=useq.WellPlate.from_str("96-well"),
    a1_center_xy=(1000, 1500),
    rotation=0.3,
)

wdg = PlateCalibrationWidget(mmcore=mmc)
wdg.setValue(plan)
wdg.show()

app.exec()
