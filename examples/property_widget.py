from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QFormLayout, QWidget

from pymmcore_widgets import PropertyWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wdg = QWidget()
wdg.setLayout(QFormLayout())

devs_pros = [
    ("Camera", "AllowMultiROI"),
    ("Camera", "Binning"),
    ("Camera", "CCDTemperature"),
]

for dev, prop in devs_pros:
    prop_wdg = PropertyWidget(dev, prop)
    wdg.layout().addRow(f"{dev}-{prop}:", prop_wdg)

wdg.show()

app.exec_()
