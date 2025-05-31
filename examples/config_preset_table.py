from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets._config_preset_table import ConfigPresetTable

core = CMMCorePlus.instance()
core.loadSystemConfiguration()

app = QApplication([])
widget = ConfigPresetTable()
widget.loadGroup("Channel")
widget.show()

app.exec_()
