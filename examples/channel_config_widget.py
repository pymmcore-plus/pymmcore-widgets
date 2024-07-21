from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import OpticalConfigDialog

core = CMMCorePlus().instance()
core.loadSystemConfiguration()
scope = Microscope.create_from_core(core)

app = QApplication([])
ocd = OpticalConfigDialog(scope.config_groups)
ocd.show()

app.exec()
