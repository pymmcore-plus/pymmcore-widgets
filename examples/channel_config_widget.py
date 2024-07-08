from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import OpticalConfigDialog

core = CMMCorePlus().instance()
core.loadSystemConfiguration(r"c:\Users\Admin\Desktop\test.cfg")
app = QApplication([])
ocd = OpticalConfigDialog()
ocd.load_group("Channel")
ocd.show()

app.exec()
