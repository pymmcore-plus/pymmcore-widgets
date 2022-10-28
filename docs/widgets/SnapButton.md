# SnapButton

::: pymmcore_widgets.SnapButton

## Examples

### Simple `SnapButton`.

```python
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import SnapButton

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

snap_btn = SnapButton()
snap_btn.show()

app.exec_()
```

### Combination of `SnapButton` with other `pymmcore-widgets`.

see [ImagePreview](ImagePreview.md#examples)
