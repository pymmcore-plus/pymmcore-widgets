from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigGroupWidget

core = CMMCorePlus().instance()
core.loadSystemConfiguration()

app = QApplication([])
ocd = ConfigGroupWidget.create_from_core(core)
ocd.resize(1080, 860)
ocd.setCurrentGroup("Channel")
ocd.show()

app.exec()
