"""Example usage of the GridPlanWidget class.

Check also the 'position_table.py' and 'mda_widget.py' examples to see the
GridPlanWidget used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import GridPlanWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

grid_wdg = GridPlanWidget()
grid_wdg.show()

app.exec()
