import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget
from pymmcore_widgets.hcs._plate_navigator_widget import PlateNavigator

app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
plate = useq.WellPlatePlan(
    plate=useq.WellPlate.from_str("96-well"),
    a1_center_xy=(1000, 1000),
    rotation=3,
)
wdg = PlateNavigator(mmcore=mmc)
wdg.set_plan(plate)
wdg.show()
stg = StageWidget("XY", mmcore=mmc)
stg._poll_cb.setChecked(True)
stg.show()
app.exec()
