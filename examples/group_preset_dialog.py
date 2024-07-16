from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import GroupPresetDialog

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

gp = GroupPresetDialog(mmcore=mmc)
gp.show()

app.exec()
