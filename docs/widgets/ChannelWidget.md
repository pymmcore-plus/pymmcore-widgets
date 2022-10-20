# ChannelWidget

::: pymmcore_widgets._channel_widget

!!! Important
    To make sure all the widgets listen to the same micromanager core, create
    one using `CMMCorePlus.instance()` or do not specify it in the widget(s).

## Examples

Simple `ChannelWidget`:
```sh
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

`ChannelWidget` used in combination with other widgets:
```sh
from typing import Optional

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from pymmcore_widgets import (
    ChannelWidget,
    ExposureWidget,
    ImagePreview,
    LiveButton,
    SnapButton,
)


class ImageFrame(QWidget):
    """An example widget with a snap/live button and an image preview."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.preview = ImagePreview()
            self.snap_button = SnapButton()
            self.live_button = LiveButton()
            self.exposure = ExposureWidget()
            self.channel = ChannelWidget()

            self.setLayout(QVBoxLayout())

            buttons = QGroupBox()
            buttons.setLayout(QHBoxLayout())
            buttons.layout().addWidget(self.snap_button)
            buttons.layout().addWidget(self.live_button)

            ch_exp = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            ch_exp.setLayout(layout)

            ch = QGroupBox()
            ch.setTitle("Channel")
            ch.setLayout(QHBoxLayout())
            ch.layout().setContentsMargins(0, 0, 0, 0)
            ch.layout().addWidget(self.channel)
            layout.addWidget(ch)

            exp = QGroupBox()
            exp.setTitle("Exposure")
            exp.setLayout(QHBoxLayout())
            exp.layout().setContentsMargins(0, 0, 0, 0)
            exp.layout().addWidget(self.exposure)
            layout.addWidget(exp)

            self.layout().addWidget(self.preview)
            self.layout().addWidget(ch_exp)
            self.layout().addWidget(buttons)


if __name__ == "__main__":
    CMMCorePlus().instance().loadSystemConfiguration()
    app = QApplication([])
    frame = ImageFrame()
    frame.show()
    app.exec_()
```
