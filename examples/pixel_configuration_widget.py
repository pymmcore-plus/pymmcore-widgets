from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication
from rich import print

from pymmcore_widgets import PixelConfigurationWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()


def _print(value: dict):
    print("\nPixel Configuration Widget value:")
    print(value)


px_wdg = PixelConfigurationWidget(title="Pixel Configuration Widget")
px_wdg.valueChanged.connect(_print)
px_wdg.show()

app.exec_()
