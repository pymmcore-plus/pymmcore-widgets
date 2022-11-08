from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ObjectivesWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

obj_wdg = ObjectivesWidget()
obj_wdg.show()

app.exec_()
