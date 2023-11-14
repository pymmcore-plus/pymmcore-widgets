from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import PixelConfigurationWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

px_wdg = PixelConfigurationWidget(title="Pixel Configuration Widget")
px_wdg.show()

app.exec_()
