from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import PropertyBrowser

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

pb_wdg = PropertyBrowser()
pb_wdg.show()

app.exec_()
