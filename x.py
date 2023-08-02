import sys

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.useq_widgets import PositionTable

app = QApplication.instance() or QApplication(sys.argv)

ch = PositionTable()
ch.show()
sys.exit(app.exec_())
