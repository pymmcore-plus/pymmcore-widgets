# ObjectivesWidget

**TODO: add image**

::: pymmcore_widgets._objective_widget

!!! Important
    To make sure all the widgets listen to the same micromanager core, create
    one using `CMMCorePlus.instance()` (and not simply `CMMCorePlus()`)
    or do not specify it in the widget(s).

## Examples

Simple `ObjectivesWidget`:
```sh
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ObjectivesWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

obj_wdg = ObjectivesWidget()
obj_wdg.show()

app.exec_()
```


In this example the default regex (used by the core `guessObjectiveDevices` method)
is replaced with a custom one before loading the `ObjectivesWidget`:
```sh
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ObjectivesWidget

app = QApplication([])

mmc = CMMCorePlus().instance()

# mmc will look for a device label matching the string 'objective'
# to select the 'objective_device'
mmc.objective_device_pattern = 'objective'

mmc.loadSystemConfiguration()

obj_wdg = ObjectivesWidget()
obj_wdg.show()

app.exec_()
```


In alternative, the `objective_device` can be directly specified
when creating the `ObjectivesWidget`:
```sh
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ObjectivesWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

obj_wdg = ObjectivesWidget('Objective')
obj_wdg.show()

app.exec_()
```
