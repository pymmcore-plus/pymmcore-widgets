from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcwizard.config_wizard import ConfigWizard

core = CMMCorePlus.instance()
app = (inst := QApplication.instance()) or QApplication([])
wiz = ConfigWizard("/Users/talley/Desktop/MMConfig_demo.cfg")
# wiz = ConfigWizard()
wiz.show()
if not inst:
    app.exec_()
