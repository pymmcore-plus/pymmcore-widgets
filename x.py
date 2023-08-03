import sys

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.useq_widgets import MDASequenceWidget

app = QApplication.instance() or QApplication(sys.argv)

wdg = MDASequenceWidget()
wdg.show()
sys.exit(app.exec_())
