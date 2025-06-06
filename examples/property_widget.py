from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QFormLayout, QWidget

from pymmcore_widgets import PropertyWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

class CustomPropertyWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        devs_pros = [
            ("Camera", "AllowMultiROI"),
            ("Camera", "Binning"),
            ("Camera", "CCDTemperature"),
        ]

        layout = QFormLayout(self)
        for dev, prop in devs_pros:
            prop_wdg = PropertyWidget(dev, prop)
            layout.addRow(f"{dev}-{prop}:", prop_wdg)

wdg = CustomPropertyWidget()
wdg.show()

app.exec()
