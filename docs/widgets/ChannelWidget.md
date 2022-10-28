# ChannelWidget

::: pymmcore_widgets.ChannelWidget

## Examples

### Simple `ChannelWidget`.

```python
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ChannelWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

ch_wdg = ChannelWidget()
ch_wdg.show()

app.exec_()
```

### Combining `ChannelWidget` with other `pymmcore-widgets`.

see [ImagePreview](ImagePreview.md#examples)
