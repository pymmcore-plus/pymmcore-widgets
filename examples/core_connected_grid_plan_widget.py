from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.mda import CoreConnectedGridPlanWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

grid_wdg = CoreConnectedGridPlanWidget()
grid_wdg.show()

app.exec_()
