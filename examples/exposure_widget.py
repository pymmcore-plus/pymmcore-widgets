"""
Check also the 'image_widget.py' example to see the
DefaultCameraExposureWidget used in combination of other widgets.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import DefaultCameraExposureWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

exp_wdg = DefaultCameraExposureWidget()
exp_wdg.show()

app.exec_()
