from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import GroupPresetTableWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

group_preset_wdg = GroupPresetTableWidget()
group_preset_wdg.show()

app.exec_()
