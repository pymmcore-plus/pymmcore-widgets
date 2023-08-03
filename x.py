import sys

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.useq_widgets import MDASequenceWidget

app = QApplication.instance() or QApplication(sys.argv)

wdg = MDASequenceWidget()
wdg.show()
wdg.resize(600, 300)
sys.exit(app.exec_())
