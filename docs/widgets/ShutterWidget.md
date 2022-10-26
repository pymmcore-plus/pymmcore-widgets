# ShutterWidget

::: pymmcore_widgets.ShuttersWidget

## Examples

```python
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

from pymmcore_widgets import ShuttersWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

shutter = ShuttersWidget("Shutter")
shutter.button_text_open = "Shutter"
shutter.button_text_closed = "Shutter"

shutter.show()

app.exec_()
```
