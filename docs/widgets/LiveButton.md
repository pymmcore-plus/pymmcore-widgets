# LiveButton

::: pymmcore_widgets.LiveButton

## Examples

### Simple `LiveButton`.

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import LiveButton

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

live_btn = LiveButton()
live_btn.show()

app.exec_()

### Combination of `LiveButton` with other `pymmcore-widgets`.

see [ImagePreview](ImagePreview.md#examples)
