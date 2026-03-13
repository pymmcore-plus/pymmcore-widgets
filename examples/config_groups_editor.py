import sys

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigGroupsEditor

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration()

cfg = ConfigGroupsEditor()
with_cfg = sys.argv[1] in ("1", "true") if len(sys.argv) > 1 else False
cfg.update_from_core(core, update_configs=with_cfg)
cfg.resize(900, 550)
cfg.show()

app.exec()
