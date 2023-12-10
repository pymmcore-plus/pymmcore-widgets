"""Example usage of the ShuttersWidget class.

In this example all the devices of type 'Shutter' that are loaded
in micromanager are displayed with a 'ShuttersWidget'.

The autoshutter checkbox is displayed only with the last shutter device.
"""


from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

from pymmcore_widgets import ShuttersWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wdg = QWidget()
wdg.setLayout(QHBoxLayout())

shutter_dev_list = list(mmc.getLoadedDevicesOfType(DeviceType.Shutter))

for idx, shutter_dev in enumerate(shutter_dev_list):
    # bool to display the autoshutter checkbox only with the last shutter
    autoshutter = bool(idx >= len(shutter_dev_list) - 1)
    shutter = ShuttersWidget(shutter_dev, autoshutter=autoshutter)
    shutter.button_text_open = shutter_dev
    shutter.button_text_closed = shutter_dev
    wdg.layout().addWidget(shutter)

wdg.show()

app.exec_()
