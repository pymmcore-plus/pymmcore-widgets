"""Example usage of the SnapButton class.

Check also the 'image_widget.py' example to see the SnapButton
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import SnapButton

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

snap_btn = SnapButton()
snap_btn.show()

app.exec_()
