from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

from pymmcore_widgets import ShuttersWidget

CFG = Path(__file__).parent.parent / "tests" / "test_config.cfg"


class Shutters(QWidget):
    """An example for a shutter widhet."""

    def __init__(self) -> None:
        super().__init__()

        shutter = ShuttersWidget("Shutter", autoshutter=False)
        shutter.button_text_open = "Shutter"
        shutter.button_text_closed = "Shutter"

        shutter1 = ShuttersWidget("Shutter")
        shutter1.button_text_open = "Shutter_1"
        shutter1.button_text_closed = "Shutter_1"

        # multishutter = ShuttersWidget("Multi Shutter")
        # multishutter.button_text_open = "Multi Shutter"
        # multishutter.button_text_closed = "Multi Shutter"

        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(5)
        self.layout().addWidget(shutter)
        # self.layout().addWidget(multishutter)
        self.layout().addWidget(shutter1)


if __name__ == "__main__":
    mmc = CMMCorePlus().instance()
    # mmc.loadSystemConfiguration(CFG)
    mmc.loadSystemConfiguration()
    mmc.setConfig("Channel", "FITC")
    app = QApplication([])
    sh = Shutters()
    sh.show()
    app.exec_()
