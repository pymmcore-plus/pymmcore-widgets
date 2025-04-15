from qtpy.QtWidgets import QApplication

from pymmcore_widgets import InstallWidget

app = QApplication([])
wdg = InstallWidget()
wdg.show()
app.exec()
