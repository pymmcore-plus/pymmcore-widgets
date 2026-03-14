import sys

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigGroupsEditor

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration()

with_cfg = sys.argv[1] in ("1", "true") if len(sys.argv) > 1 else False
cfg = ConfigGroupsEditor.create_from_core(core, load_configs=with_cfg)
cfg.resize(900, 550)
cfg.show()

app.exec()
