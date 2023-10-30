"""Example usage of the ChannelTable class.

Check also the 'mda_widget.py' example to see the ChannelTable
used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.old_mda import OldChannelTable

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

ch_table_wdg = OldChannelTable()
ch_table_wdg.show()

app.exec_()