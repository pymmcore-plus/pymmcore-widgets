from qtpy.QtWidgets import QApplication

from pymmcore_widgets import InstallWidget

app = QApplication([])
window = InstallWidget()
window.show()
app.exec_()
