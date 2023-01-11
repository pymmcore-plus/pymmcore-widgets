"""Example usage of the TimePlanWidget class.

Check also the 'mda_widget.py' example to see the TimePlanWidget
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import TimePlanWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

t_wdg = TimePlanWidget()
t_wdg.show()

app.exec_()
