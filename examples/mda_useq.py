from qtpy.QtWidgets import QApplication

from pymmcore_widgets.useq_widgets import MDASequenceWidget

app = QApplication([])

wdg = MDASequenceWidget()
wdg.show()
wdg.valueChanged.connect(lambda: print(wdg.value()))
app.exec()
