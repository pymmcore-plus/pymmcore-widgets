from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import GroupPresetTableWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()
mmc.events.configDefined.connect(lambda *args: print("Config defined:", args))
mmc.events.configGroupDeleted.connect(lambda name: print("Config group deleted:", name))
mmc.events.configGroupChanged.connect(lambda name: print("Config group changed:", name))
mmc.events.configDeleted.connect(lambda *args: print("Config deleted:", args))
mmc.events.channelGroupChanged.connect(
    lambda name: print("Channel group changed:", name)
)

group_preset_wdg = GroupPresetTableWidget()
group_preset_wdg.show()

app.exec()
