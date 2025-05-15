from qtpy.QtWidgets import QApplication

from pymmcore_widgets import CoreLogWidget

app = QApplication([])
wdg = CoreLogWidget()
wdg.show()
app.exec()
