import useq
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.useq_widgets import MDASequenceWidget

app = QApplication([])

wdg = MDASequenceWidget()
wdg.time_plan.setValue(useq.TIntervalLoops(interval=0.5, loops=11))

wdg.show()
# wdg.channels.setChannelGroups({"Channel": ["DAPI", "FITC"], "Other": ["foo", "bar"]})
# wdg.valueChanged.connect(lambda: print(wdg.value()))
app.exec()
