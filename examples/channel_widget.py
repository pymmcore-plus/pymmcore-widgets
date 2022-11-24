"""Example usage of the ChannelWidget class.

Check also the 'image_widget.py' example to see the ChannelWidget
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ChannelWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

ch_wdg = ChannelWidget()
ch_wdg.show()

app.exec_()
