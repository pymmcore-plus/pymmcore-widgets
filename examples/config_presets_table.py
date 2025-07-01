from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication
from rich import print

from pymmcore_widgets.config_presets import ConfigPresetsTable

app = QApplication([])

core = CMMCorePlus()
core.loadSystemConfiguration()

table = ConfigPresetsTable.create_from_core(core)
table.setGroup("Channel")
model = table.sourceModel()
assert model


@model.dataChanged.connect
def _on_data_changed():
    print(model.get_groups()[1])  # channel group


table.resize(800, 200)
table.show()

app.exec()
