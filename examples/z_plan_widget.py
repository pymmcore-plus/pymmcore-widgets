"""Example usage of the ZPlanWidget class.

Check also the 'mda_widget.py' example to see the ZPlanWidget
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ZPlanWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

z_wdg = ZPlanWidget()
z_wdg.show()

app.exec()
