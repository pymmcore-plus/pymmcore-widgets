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





## Widgets

The following widgets are currently available:

| Method      | Description                          |
| ----------- | ------------------------------------ |
| [CameraRoiWidget](./widgets/CameraRoiWidget.md)           | A Widget to control the camera device ROI.|
| [ChannelWidget](./widgets/ChannelWidget.md)               | My favorite widget |
| [ConfigurationWidget](./widgets/ConfigurationWidget.md)   | My favorite widget |
| [DefaultCameraExposureWidget](./widgets/DefaultCameraExposureWidget.md)   | My favorite widget |
| [ExposureWidget](./widgets/ExposureWidget.md)             | My favorite widget |
| [DeviceWidget](./widgets/DeviceWidget.md)                 | My favorite widget |
| [GroupPresetTableWidget](./widgets/GroupPresetTableWidget.md)             | My favorite widget |
| [ImagePreview](./widgets/ImagePreview.md)                 | My favorite widget |
| [LiveButton](./widgets/LiveButton.md)                     | My favorite widget |
| [ObjectivesWidget](./widgets/ObjectivesWidget.md)         | My favorite widget |
| [PixelSizeWidget](./widgets/PixelSizeWidget.md)           | My favorite widget |
| [PresetsWidget](./widgets/PresetsWidget.md)               | My favorite widget |
| [PropertyBrowser](./widgets/PropertyBrowser.md)           | My favorite widget |
| [PropertyWidget](./widgets/PropertyWidget.md)             | My favorite widget |
| [ShutterWidget](./widgets/ShutterWidget.md)               | My favorite widget |
| [SliderDialog](./widgets/SliderDialog.md)                 | My favorite widget |
| [SnapButton](./widgets/SnapButton.md)                     | My favorite widget |
| [StageWidget](./widgets/StageWidget.md)                   | My favorite widget |
| [StateDeviceWidget](./widgets/StateDeviceWidget.md)       | My favorite widget |
| [MDADWidget](./widgets/MDAWidget.md)                      | My favorite widget |

In progress:

* [HCSWidget](./widgets/HCSWidget.md)
* [SampleExplorerWidget](./widgets/SampleExplorerWidget.md)

## Usage

For code examples: [examples](https://github.com/pymmcore-plus/pymmcore-widgets/tree/main/examples).

For a pre-made user interface, see [napari-micromanager](https://pypi.org/project/napari-micromanager/) ([github](https://github.com/pymmcore-plus/napari-micromanager)).
