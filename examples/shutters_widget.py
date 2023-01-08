from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ShuttersWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

shutter = ShuttersWidget("White Light Shutter")
shutter.button_text_open = "White Light Shutter"
shutter.button_text_closed = "White Light Shutter"
shutter.show()

app.exec_()
