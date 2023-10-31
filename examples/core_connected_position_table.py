"""Example usage of the PositionTable class.

Check also the 'mda_widget.py' example to see the PositionTable
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.mda import CoreConnectedPositionTable

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

pos_wdg = CoreConnectedPositionTable(rows=3)
pos_wdg.use_af.setChecked(True)
pos_wdg.resize(600, 200)
pos_wdg.show()

app.exec_()
