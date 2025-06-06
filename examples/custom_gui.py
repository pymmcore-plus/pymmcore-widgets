# Import the necessary packages
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QGridLayout, QWidget

from pymmcore_widgets import (
    ChannelGroupWidget,
    ChannelWidget,
    ConfigurationWidget,
    DefaultCameraExposureWidget,
    ImagePreview,
    LiveButton,
    SnapButton,
)


# Create a QWidget class named MyWidget
class MyWidget(QWidget):
    """An example QWidget that uses some of the widgets in pymmcore_widgets."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        # This is not strictly necessary but we can create a Micro-Manager core
        # instance so that all the widgets can control the same core. If you don't
        # create a core instance, the first widget to be instantiated will create
        # a new core instance.
        CMMCorePlus.instance()

        # Create the wanted pymmcore_widgets
        cfg = ConfigurationWidget()
        ch_group_combo = ChannelGroupWidget()
        ch_combo = ChannelWidget()
        exp = DefaultCameraExposureWidget()
        preview = ImagePreview()
        snap = SnapButton()
        live = LiveButton()

        # Create the layout for MyWidget
        # In Qt, a `layout` (https://doc.qt.io/qt-6/layout.html) is used to add
        # widgets to a `QWidget`. For this example, we'll employ a
        # `QGridLayout` (https://doc.qt.io/qt-6/qgridlayout.html) to organize the
        # widgets in a grid-like arrangement.
        layout = QGridLayout(self)

        # Add the wanted pymmcore_widgets to the layout.
        # The first two arguments of 'addWidget' specify the grid position
        # in terms of rows and columns. The third and fourth arguments
        # define the span of the widget across multiple rows and columns.
        layout.addWidget(cfg, 0, 0, 1, 3)
        layout.addWidget(ch_group_combo, 1, 0)
        layout.addWidget(ch_combo, 1, 1)
        layout.addWidget(exp, 1, 2)
        layout.addWidget(preview, 2, 0, 1, 3)
        layout.addWidget(snap, 3, 1)
        layout.addWidget(live, 3, 2)


# Create a QApplication and show MyWidget
if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    widget = MyWidget()
    widget.show()
    app.exec()
