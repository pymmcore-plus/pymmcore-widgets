from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import SnapButton

# see also image_widget.py
app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

snap_btn = SnapButton()
snap_btn.show()

app.exec_()
