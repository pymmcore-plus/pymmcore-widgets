from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcwizard.config_wizard import ConfigWizard

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wiz = ConfigWizard()
wiz.show()

app.exec_()
