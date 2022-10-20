# ConfigurationWidget

::: pymmcore_widgets._load_system_cfg_widget

!!! Important
    To make sure all the widgets listen to the same micromanager core, create
    one using `CMMCorePlus.instance()` or do not specify it in the widget(s).

## Examples

Simple `ConfigurationWidget`:
```sh
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigurationWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

cfg_wdg = ConfigurationWidget()
cfg_wdg.show()

app.exec_()
```
