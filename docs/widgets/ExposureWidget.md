# ExposureWidget

::: pymmcore_widgets.ExposureWidget

## Examples

### Simple `ExposureWidget`.

```python
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ExposureWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

exp_wdg = ExposureWidget()
exp_wdg.show()

app.exec_()
```

### Combining `ExposureWidget` with other `pymmcore-widgets`.

see [ImagePreview](ImagePreview.md#examples)
