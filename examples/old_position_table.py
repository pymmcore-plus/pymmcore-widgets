"""Example usage of the PositionTable class.

Check also the 'mda_widget.py' example to see the PositionTable
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import OldPositionTable

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

pos_wdg = OldPositionTable()
pos_wdg.show()

app.exec_()
