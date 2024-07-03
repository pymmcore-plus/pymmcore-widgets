from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import OpticalConfigDialog

core = CMMCorePlus().instance()
core.loadSystemConfiguration()
app = QApplication([])
ocd = OpticalConfigDialog()
ocd.show()

app.exec_()
