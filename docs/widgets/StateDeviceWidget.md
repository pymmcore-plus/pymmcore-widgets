# StateDeviceWidget

**TODO: add image**

::: pymmcore_widgets._device_widget.StateDeviceWidget

!!! Important
    To make sure all the widgets listen to the same micromanager core, create
    one using `CMMCorePlus.instance()` (and not simply `CMMCorePlus()`)
    or do not specify it in the widget(s).

## Examples

In this example all the devices of type `StateDevice` that are loaded in micromanager
are dysplaied with a `StateDeviceWidget`:

```sh
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
```

An identical result can be obtained using the `DeviceWidget.for_device('device_label')`
method (see [DeviceWidget](DeviceWidget.md)).
