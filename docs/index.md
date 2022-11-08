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
| [ChannelWidget](./widgets/ChannelWidget.md)               | A QComboBox-based widget to select which micromanager channel configuration to use. |
| [ConfigurationWidget](./widgets/ConfigurationWidget.md)   | A Widget to select and load a micromanager system configuration. |
| [DefaultCameraExposureWidget](./widgets/DefaultCameraExposureWidget.md)   | A Widget to get/set exposure on the default camera. |
| [ExposureWidget](./widgets/ExposureWidget.md)             | A Widget to get/set exposure on a camera. |
| [DeviceWidget](./widgets/DeviceWidget.md)                 | A general Device Widget. |
| [GroupPresetTableWidget](./widgets/GroupPresetTableWidget.md)             | A Widget to create, edit, delete and set micromanager group presets. |
| [ImagePreview](./widgets/ImagePreview.md)                 |  A Widget that displays the last image snapped by active core. |
| [LiveButton](./widgets/LiveButton.md)                     | A Widget to create a two-state (on-off) live mode QPushButton. |
| [ObjectivesWidget](./widgets/ObjectivesWidget.md)         | A QComboBox-based Widget to select the microscope objective. |
| [PixelSizeWidget](./widgets/PixelSizeWidget.md)           | Create a QTableWidget to set pixel size configurations. |
| [PresetsWidget](./widgets/PresetsWidget.md)               | A Widget to create a QCombobox containing the presets of the specified group. |
| [PropertyBrowser](./widgets/PropertyBrowser.md)           | A Widget to browse and change properties of all devices. |
| [PropertyWidget](./widgets/PropertyWidget.md)             | A widget that presents a view onto an mmcore device property. |
| [ShutterWidget](./widgets/ShutterWidget.md)               | A Widget for shutters and Micro-Manager autoshutter. |
| [SliderDialog](./widgets/SliderDialog.md)                 | A Widget that shows range-based properties (such as light sources) as sliders. |
| [SnapButton](./widgets/SnapButton.md)                     | A Widget to csreate a snap QPushButton linked to the `CMMCorePlus` snap method. |
| [StageWidget](./widgets/StageWidget.md)                   | A Widget to control a XY and/or a Z stage. |
| [StateDeviceWidget](./widgets/StateDeviceWidget.md)       | A Widget with a QComboBox to control the states of a StateDevice. |
| [MDAWidget](./widgets/MDAWidget.md)                      | A Multi-dimensional acquisition Widget. |

In progress:

* [HCSWidget](./widgets/HCSWidget.md)
* [SampleExplorerWidget](./widgets/SampleExplorerWidget.md)

## Usage

For a pre-made user interface, see [napari-micromanager](https://pypi.org/project/napari-micromanager/) ([github](https://github.com/pymmcore-plus/napari-micromanager)).

Detailed description and usage of each Widget is explained in their [respective pages](#widgets).
