from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QPushButton
from rich import print

from pymmcore_widgets import ConfigGroupsEditor

core = CMMCorePlus().instance()
core.loadSystemConfiguration()

app = QApplication([])

ocd = ConfigGroupsEditor.create_from_core(core)
ocd.resize(1080, 860)
ocd.setCurrentGroup("Channel")
ocd.show()

btn = QPushButton("Print Current Data")
btn.clicked.connect(lambda: print(ocd.data()))
ocd.layout().children()[0].addWidget(btn)  # Add button to the layout

app.exec()
