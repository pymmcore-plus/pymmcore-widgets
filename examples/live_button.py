from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import LiveButton

# see also image_widget.py
app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

live_btn = LiveButton()
live_btn.show()

app.exec_()
