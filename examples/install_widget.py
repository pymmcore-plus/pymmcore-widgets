from qtpy.QtWidgets import QApplication

from pymmcore_widgets import InstallWidget

app = QApplication([])
wdg = InstallWidget()
wdg.show()
wdg.resize(700, 250)
app.exec()
