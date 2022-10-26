# DeviceWidget

::: pymmcore_widgets.DeviceWidget

!!! Note
    Currently, `DeviceWidget` only supports devices of type `StateDevice`. Calling
    `DeviceWidget.for_device("device_label")`, will create the `DeviceWidget` subclass
    [StateDeviceWidget](StateDeviceWidget.md).

## Examples

### Load all devices of type `StateDevice`.

In this example all the devices of type `StateDevice` that are loaded in micromanager
are dysplaied with a `DeviceWidget`.

```python
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import QApplication, QFormLayout, QWidget

from pymmcore_widgets import DeviceWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wdg = QWidget()
wdg.setLayout(QFormLayout())

for d in mmc.getLoadedDevicesOfType(DeviceType.StateDevice):
    dev_wdg = DeviceWidget.for_device(d)
    wdg.layout().addRow(f"{d}:", dev_wdg)

wdg.show()

app.exec_()
```
