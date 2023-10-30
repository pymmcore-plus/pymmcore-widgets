"""Example usage of the ZStackWidget class.

Check also the 'mda_widget.py' example to see the ZStackWidget
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.mda import CoreConnectedZPlanWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

z_wdg = CoreConnectedZPlanWidget()
z_wdg.show()

app.exec_()