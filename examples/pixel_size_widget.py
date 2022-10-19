from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import PixelSizeWidget

CFG = Path(__file__).parent.parent / "tests" / "test_config.cfg"

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration(CFG)

px_wdg = PixelSizeWidget()
px_wdg.show()

app.exec_()
