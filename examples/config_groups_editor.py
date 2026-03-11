from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigGroupsEditor

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration()

cfg = ConfigGroupsEditor()
cfg.update_from_core(core, update_configs=False)
cfg.resize(900, 550)
cfg.show()

app.exec()
