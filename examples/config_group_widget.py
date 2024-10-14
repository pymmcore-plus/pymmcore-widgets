from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import QApplication
from rich import print

from pymmcore_widgets import ConfigGroupWidget

core = CMMCorePlus().instance()
core.loadSystemConfiguration()
scope = Microscope.create_from_core(core)
print(scope.config_groups)
app = QApplication([])
ocd = ConfigGroupWidget(scope.config_groups)
ocd.update_options_from_core(core)
ocd.setCurrentGroup("Channel")
ocd.show()

app.exec()
