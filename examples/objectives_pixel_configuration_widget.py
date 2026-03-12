from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ObjectivesPixelConfigurationWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

px_wdg = ObjectivesPixelConfigurationWidget()
px_wdg.show()

app.exec()
