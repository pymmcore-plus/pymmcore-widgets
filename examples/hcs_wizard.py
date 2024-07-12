from contextlib import suppress

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

with suppress(ImportError):
    from rich import print


from pymmcore_widgets.hcs import HCSWizard

app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
w = HCSWizard()
w.show()
w.valueChanged.connect(print)
w.accepted.connect(print)

app.exec()
