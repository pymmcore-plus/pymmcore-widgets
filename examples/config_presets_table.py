from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.config_presets import ConfigPresetsTable

app = QApplication([])

core = CMMCorePlus()
core.loadSystemConfiguration()

table = ConfigPresetsTable.create_from_core(core)
table.setGroup("Channel")
table.resize(800, 200)
table.show()

app.exec()
