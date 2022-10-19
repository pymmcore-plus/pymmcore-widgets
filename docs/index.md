## Overview

[pymmcore-widgets](https://pypi.org/project/pymmcore-widgets/) is a library of [PyQt](https://riverbankcomputing.com/software/pyqt/)/[PySide](https://www.qt.io/qt-for-python) widgets that can be used in combination with [pymmcore-plus](https://pypi.org/project/pymmcore-plus/) ([github](https://github.com/pymmcore-plus/pymmcore-plus)) to build custom user interfaces for [micromanager](https://micro-manager.org) in a python/Qt environment.


## Installation

```sh
pip install pymmcore-widgets
```

!!! Important
    This package does **NOT** include a [PyQt](https://riverbankcomputing.com/software/pyqt/)/[PySide](https://www.qt.io/qt-for-python) backend, you must install one yourself (e.g. ```pip install PyQt5```).

!!! Note
    Widgets are tested on:

    * `macOS & Windows`
    * `Python 3.8, 3.9 & 3.10`
    * `PyQt5 & PyQt6`
    * `PySide2 & PySide6`



## Usage
See each [widget respective page](#widgets) for a detailed description and usage.

For code examples: [examples](https://github.com/pymmcore-plus/pymmcore-widgets/tree/main/examples).

For a pre-made user interface, see [napari-micromanager](https://pypi.org/project/napari-micromanager/) ([github](https://github.com/pymmcore-plus/napari-micromanager)).



## Widgets

The following widgets are currently available:

* [ChannelWidget](./widgets/ChannelWidget.md)
* [ConfigurationWidget](./widgets/ConfigurationWidget.md)
* [DefaultCameraExposureWidget](./widgets/DefaultCameraExposureWidget.md)
* [DeviceWidget](./widgets/DeviceWidget.md)
* [GroupPresetTableWidget](./widgets/GroupPresetTableWidget.md)
* [ImagePreview](./widgets/ImagePreview.md)
* [LiveButton](./widgets/LiveButton.md)
* [ObjectivesWidget](./widgets/ObjectivesWidget.md)
* [PresetsWidget](./widgets/PresetsWidget.md)
* [PropertyBrowser](./widgets/PropertyBrowser.md)
* [PropertyWidget](./widgets/PropertyWidget.md)
* [SliderDialog](./widgets/SliderDialog.md)
* [SnapButton](./widgets/SnapButton.md)
* [StageWidget](./widgets/StageWidget.md)
* [StateDeviceWidget](./widgets/StateDeviceWidget.md)

In progress:

* [CameraRoiWidget](./widgets/CameraRoiWidget.md)
* [HCSWidget](./widgets/HCSWidget.md)
* [MultiDWidget](./widgets/MultiDWidget.md)
* [PixelSizeWidget](./widgets/PixelSizeWidget.md)
* [SampleExplorerWidget](./widgets/SampleExplorerWidget.md)
* [ShutterWidget](./widgets/ShutterWidget.md)




<!-- # Welcome to MkDocs

For full documentation visit [mkdocs.org](https://www.mkdocs.org).

## Commands

* `mkdocs new [dir-name]` - Create a new project.
* `mkdocs serve` - Start the live-reloading docs server.
* `mkdocs build` - Build the documentation site.
* `mkdocs -h` - Print help message and exit.

## Project layout

    mkdocs.yml    # The configuration file.
    docs/
        index.md  # The documentation homepage.
        ...       # Other markdown pages, images and other files. -->
