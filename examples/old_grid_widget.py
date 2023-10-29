from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.old_mda import OldGridWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

grid_wdg = OldGridWidget()
grid_wdg.show()

app.exec_()
