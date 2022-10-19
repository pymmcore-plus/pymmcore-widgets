from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QFormLayout, QWidget

from pymmcore_widgets import PropertyWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

dev_prop = [
    ("Camera", "AllowMultiROI"),
    ("Camera", "Binning"),
    ("Camera", "CCDTemperature"),
]

wdg = QWidget()
wdg.setLayout(QFormLayout())

for dev, prop in dev_prop:
    prop_wdg = PropertyWidget(dev, prop)
    wdg.layout().addRow(f"{dev}-{prop}:", prop_wdg)

wdg.show()

app.exec_()
