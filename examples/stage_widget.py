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
wdg_layout = QHBoxLayout(wdg)

stages = list(mmc.getLoadedDevicesOfType(DeviceType.XYStage))
stages.extend(mmc.getLoadedDevicesOfType(DeviceType.Stage))
for stage in stages:
    lbl = "Z" if mmc.getDeviceType(stage) == DeviceType.Stage else "XY"
    bx = QGroupBox(f"{lbl} Control")
    bx_layout = QHBoxLayout(bx)
    bx_layout.setContentsMargins(0, 0, 0, 0)
    bx_layout.addWidget(StageWidget(device=stage, position_label_below=True))
    wdg_layout.addWidget(bx)


wdg.show()
app.exec()
