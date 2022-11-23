from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ShuttersWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

shutter = ShuttersWidget("Shutter")
shutter.button_text_open = "Shutter"
shutter.button_text_closed = "Shutter"
shutter.show()

app.exec_()
