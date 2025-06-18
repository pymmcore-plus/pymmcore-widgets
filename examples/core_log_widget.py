from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import CoreLogWidget

app = QApplication([])
core = CMMCorePlus()

wdg = CoreLogWidget(mmcore=core)
wdg.clear()
wdg.show()

core.loadSystemConfiguration()
app.exec()
