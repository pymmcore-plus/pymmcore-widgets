"""MDAWidget is a widget for creating and running a useq.MDASequence.

It is fully connected to the CMMCorePlus object, and has a "run" button.
"""

from contextlib import suppress

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import MDAWidget, PropertyBrowser

with suppress(ImportError):
    from rich import print

app = QApplication([])

CMMCorePlus.instance().loadSystemConfiguration()

p = PropertyBrowser()
p.show()

wdg = MDAWidget()
wdg.channels.setChannelGroups({"Channel": ["DAPI", "FITC"]})
wdg.time_plan.setValue(useq.TIntervalLoops(interval=0.5, loops=11))
wdg.valueChanged.connect(lambda: print(wdg.value()))
wdg.show()
app.exec()
