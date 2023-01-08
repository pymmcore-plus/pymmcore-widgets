"""Example usage of the StateDeviceWidget class.

In this example all the devices of type 'StateDevice' that are loaded in micromanager
are displayed with a 'StateDeviceWidget'.
"""

from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import QApplication, QFormLayout, QWidget

from pymmcore_widgets import StateDeviceWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wdg = QWidget()
wdg.setLayout(QFormLayout())

for d in mmc.getLoadedDevicesOfType(DeviceType.StateDevice):
    state_dev_wdg = StateDeviceWidget(d)
    wdg.layout().addRow(f"{d}:", state_dev_wdg)

wdg.show()

app.exec_()
