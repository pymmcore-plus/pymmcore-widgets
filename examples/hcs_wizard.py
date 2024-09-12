from contextlib import suppress

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget

with suppress(ImportError):
    from rich import print

from pymmcore_widgets.hcs import HCSWizard

app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
w = HCSWizard()
w.show()
w.accepted.connect(lambda: print(w.value()))
s = StageWidget("XY", mmcore=mmc)
s.show()


plan = useq.WellPlatePlan(
    plate=useq.WellPlate.from_str("96-well"),
    a1_center_xy=(1000, 1500),
    rotation=0.3,
)
w.setValue(plan)

app.exec()
