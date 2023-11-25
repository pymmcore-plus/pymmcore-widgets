# installation

!!! mention conda/mamba

You can install the latest release of [pymmcore-widgets](https://pypi.org/project/pymmcore-widgets/) using pip:

```sh
pip install pymmcore-widgets
```

This package relies on either the [PyQt](https://riverbankcomputing.com/software/pyqt/) or [PySide](https://www.qt.io/qt-for-python) libraries. Ensure to install one of these dependencies prior to using the package (it has been tested with `PyQt5`, `PyQt6`,`PySide2` & `PySide6`).

For example, to install [PyQt6](https://riverbankcomputing.com/software/pyqt/download), you can use:

```sh
pip install PyQt6
```

!!! mention that this is installing pymmcore-plus as well but that you need to install the [Micro-Manager adapters](https://pymmcore-plus.github.io/pymmcore-plus/install/#installing-micro-manager-device-adapters) yourself.



# getting started

- you can specify which Micro-Manager core instance to use. If not specified, each widget will use the the active one or will create a new instance if none is active. If you want to create a core yourself, we suggest to use CMMCorePlus.instance() if you want all widget to listen to the same core instance. 

```python
# import the necessary packages
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


class MyWidget(QWidget):
    """An example QWidget that uses some of the widgets in pymmcore_widgets."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        # create the wanted pymmcore_widgets
        cfg = ConfigurationWidget()
        ch_group_combo = ChannelGroupWidget()
        ch_combo = ChannelWidget()
        exp = DefaultCameraExposureWidget()
        preview = ImagePreview()
        snap = SnapButton()
        live = LiveButton()

        # set the MyWidget layout
        layout = QGridLayout(self)

        # add the wanted pymmcore_widgets to the layout
        layout.addWidget(cfg, 0, 0, 1, 3)
        layout.addWidget(ch_group_combo, 1, 0)
        layout.addWidget(ch_combo, 1, 1)
        layout.addWidget(exp, 1, 2)
        layout.addWidget(preview, 2, 0, 1, 3)
        layout.addWidget(snap, 3, 1)
        layout.addWidget(live, 3, 2)


# create a QApplication and show MyWidget
if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    widget = MyWidget()
    widget.show()
    app.exec_()
```

The code above will create a Qt application that looks like this:
![MyWidget](./images/my_widget_example.png)



!!! note that at the moment we don't have any mda viewer but it is on development. If you want to see the acquired images, you need to create a viewer yourself. For example, you can use [napari](https://napari.org/) and have a look at napari-micromanager.
