
## **Installation**

### Installing pymmcore-widgets

You can install the latest release of [pymmcore-widgets](https://pypi.org/project/pymmcore-widgets/) using pip:

```sh
pip install pymmcore-widgets
```

### Installing PyQt/PySide

Since [pymmcore-widgets](./index.md) relies on either the [PyQt](https://riverbankcomputing.com/software/pyqt/) or [PySide](https://www.qt.io/qt-for-python) libraries, you also **need** to install one of these packages. You can use any of the available versions of these libraries, [PyQt5](https://pypi.org/project/PyQt5/), [PyQt6](https://pypi.org/project/PyQt6/), [PySide2](https://pypi.org/project/PySide2/) or [PySide6](https://pypi.org/project/PySide6/). For example, to install [PyQt6](https://riverbankcomputing.com/software/pyqt/download), you can use:

```sh
pip install PyQt6
```

### Installing Micro-Manager

The installation of the `pymmcore-widgets` package automatically includes [pymmcore-plus](https://pymmcore-plus.github.io/pymmcore-plus), as it is a key dependency for `pymmcore-widgets`. However, you still need to install [Micro-Manager](https://micro-manager.org/) yourself (in particular the `Micro-Manager` device adapters). You can do that using the [pymmcore-plus command line tool](https://pymmcore-plus.github.io/pymmcore-plus/install/#installing-micro-manager-device-adapters) or manually from the [Micro-Manager](https://micro-manager.org/Micro-Manager_Nightly_Builds) website.

!!! Note
    If using the mauanl installation method, be sure to download the **latest nightly build** or you might get an `adapter device error`similar to [this one](#incompatible-device-interface-version).

It is quite easy to install the latest release of `Micro-Manager` using the `pymmcore-plus` command line tool. `Micro-Manager` will be downloaded and installed in the the `pymmcore-plus` folder simply by running:

```sh
mmcore install
```

To see which `Micro-Manager` installation `pymmcore-plus` is using, you can run:

```sh
mmcore list
```

To manually specify the `Micro-Manager` installation that `pymmcore-plus` should use, you can set the `MICROMANAGER_PATH` environment variable:

```sh
export MICROMANAGER_PATH=/path/to/installation
```

For more information on `pymmcore-plus` installation, visit the [pymmcore-plus documentation page](https://pymmcore-plus.github.io/pymmcore-plus/install/#installing-micro-manager-device-adapters).


## **Usage**

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


## **Troubleshooting**

### PyQt or PySide errors
```sh
qtpy.QtBindingsNotFoundError: No Qt bindings could be found
```

If you get an error similar to the one above, it means that you did not install one of the necessary [PyQt](https://riverbankcomputing.com/software/pyqt/) or [PySide](https://www.qt.io/qt-for-python) libraries (for example, you can run `pip install PyQt6` to install [PyQt6](https://pypi.org/project/PyQt6/)).

See the [installation](#installing-pyqtpyside) section for more details.


### Micro-Manager errors

#### *Micro-Manager directory not found*
```sh
pymmcore-plus - ERROR - (_util.py:131) could not find micromanager directory. Please run 'mmcore install'
```

If you tried to create a [CMMCorePlus](https://pymmcore-plus.github.io/pymmcore-plus/api/cmmcoreplus/#pymmcore_plus.core._mmcore_plus.CMMCorePlus) instance and got an error similar the on above, it probably means that you don't have `Micro-Manager` installed on your computer (for example, you can run `mmcore install` to install the latest version of `Micro-Manager`).

See the [installing Micro-Manager](#installing-micro-manager) section for more details.


#### *Incompatible device interface version*
```sh
OSError: Line 7: Device,DHub,DemoCamera,DHub
Failed to load device "DHub" from adapter module "DemoCamera" [ Failed to load device adapter "DemoCamera" from "/Users/fdrgsp/Library/Application Support/pymmcore-plus/mm/Micro-Manager-2.0.1-20210715/libmmgr_dal_DemoCamera" [ Incompatible device interface version (required = 71; found = 70) ] ]
```

If you create a [CMMCorePlus](https://pymmcore-plus.github.io/pymmcore-plus/api/cmmcoreplus/#pymmcore_plus.core._mmcore_plus CMMCorePlus) instance and you get an error similar the one above when trying to load a `Micro-Manager` configuration file, you need to **update** your `Micro-Manager` device adapters installation to the newest version (for example by running: `mmcore install`).

See the [installing Micro-Manager](#installing-micro-manager) section or the [pymmcore-plus installation documentation](https://pymmcore-plus.github.io/pymmcore-plus/install/#installing-micro-manager-device-adapters) for more details.


