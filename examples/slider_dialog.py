from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import SliderDialog

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

sl_wdg = SliderDialog("TestProperty")
sl_wdg.show()

app.exec_()
