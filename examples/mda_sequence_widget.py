import useq
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import MDASequenceWidget

app = QApplication([])

wdg = MDASequenceWidget()
wdg.channels.setChannelGroups({"Channel": ["DAPI", "FITC"]})
wdg.time_plan.setValue(useq.TIntervalLoops(interval=0.5, loops=11))
wdg.valueChanged.connect(lambda: print(wdg.value()))
wdg.show()
app.exec()
