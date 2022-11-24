"""Example usage of the StageWidget class.

In this example all the devices of type 'Stage' and 'XYStage' that are loaded
in micromanager are displayed with a 'StageWidget'.
"""


from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QWidget

from pymmcore_widgets import StageWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wdg = QWidget()
wdg.setLayout(QHBoxLayout())

stage_dev_list = list(mmc.getLoadedDevicesOfType(DeviceType.XYStage))
stage_dev_list.extend(iter(mmc.getLoadedDevicesOfType(DeviceType.Stage)))

for stage_dev in stage_dev_list:
    if mmc.getDeviceType(stage_dev) is DeviceType.XYStage:
        bx = QGroupBox("XY Control")
        bx.setLayout(QHBoxLayout())
        bx.layout().addWidget(StageWidget(device=stage_dev))
        wdg.layout().addWidget(bx)
    if mmc.getDeviceType(stage_dev) is DeviceType.Stage:
        bx = QGroupBox("Z Control")
        bx.setLayout(QHBoxLayout())
        bx.layout().addWidget(StageWidget(device=stage_dev))
        wdg.layout().addWidget(bx)

wdg.show()

app.exec_()
