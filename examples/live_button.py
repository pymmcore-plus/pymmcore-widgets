"""Example usage of the LiveButton class.

Check also the 'image_widget.py' example to see the LiveButton
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import LiveButton

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

live_btn = LiveButton()
live_btn.show()

app.exec_()
