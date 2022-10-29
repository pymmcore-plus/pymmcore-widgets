from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigurationWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

cfg_wdg = ConfigurationWidget()
cfg_wdg.show()

app.exec_()
