# Getting Started

## Installation

### Installing pymmcore-widgets

You can install the latest release of [pymmcore-widgets](https://pypi.org/project/pymmcore-widgets/) using pip:

```sh
pip install pymmcore-widgets
```

### Installing PyQt or PySide

Since [pymmcore-widgets](./index.md) relies on either the [PyQt](https://riverbankcomputing.com/software/pyqt/) or [PySide](https://www.qt.io/qt-for-python) libraries, you also **need** to install one of these packages. You can use any of the available versions of these libraries: [PyQt5](https://pypi.org/project/PyQt5/), [PyQt6](https://pypi.org/project/PyQt6/), [PySide2](https://pypi.org/project/PySide2/) or [PySide6](https://pypi.org/project/PySide6/). For example, to install [PyQt6](https://riverbankcomputing.com/software/pyqt/download), you can use:

```sh
pip install PyQt6
```

!!! Note
    Widgets are tested on:

    * `macOS & Windows`
    * `Python 3.8, 3.9 3.10 & 3.11`
    * `PyQt5 & PyQt6`
    * `PySide2 & PySide6`

### Installing Micro-Manager

The installation of the `pymmcore-widgets` package automatically includes [pymmcore-plus](https://pymmcore-plus.github.io/pymmcore-plus), as it is a key dependency for `pymmcore-widgets`. However, you still need to install the `Micro-Manager` device adapters and C++ core provided by [mmCoreAndDevices](https://github.com/micro-manager/mmCoreAndDevices#mmcoreanddevices). This can be done by following the steps described in the `pymmcore-plus` [documentation page](https://pymmcore-plus.github.io/pymmcore-plus/install/#installing-micro-manager-device-adapters).

## Usage

For a deeper understanding of each widget's functionality, refer to their [individual documentation](./widgets/CameraRoiWidget.md/) pages, where we provide short examples of usage.

### Basic usage

As shown in the example from the [Overview](./index.md#usage) section, for a basic usage of any of the widgets we need to:

1. create a Qt Application.
2. create a Micro-Manager [core](https://pymmcore-plus.github.io/pymmcore-plus/api/cmmcoreplus/#pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance) instance so that all the widgets will control the same core.
3. load a configuration file.
4. create and show the wanted widget(s).

In this example, we substitute step 3 with the [ConfigurationWidget](./widgets/ConfigurationWidget/) widget which enables us to load any `Micro-Manager` configuration file. Additionally, we use the [GroupPresetTableWidget](./widgets/GroupPresetTableWidget/) widget, which provides an interactive interface for the `groups` and `presets` stored in the configuration file.

```python title="basic_usage.py"
--8<-- "examples/basic_usage.py"
```

The code above will create a Qt Application with the `ConfigurationWidget` and `GroupPresetTableWidget`:

![type:video](./images/basic_usage.mp4){: style='width: 100%'}

!!! Note "Choosing a `Micro-Manager` core"
    Most widgets, by default, utilize the [global singleton core](https://pymmcore-plus.github.io/pymmcore-plus/api/cmmcoreplus/#pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance) or instantiate a new one if none exists. Once instantiated, the global singleton core can be accessed using `CMMCorePlus.instance()`. This eliminates the need for manual core instance creation.

    For example, in the case above, the `ConfigurationWidget` is the first widget to be instantiated and it will automatically create a new core instance. This makes the `mmc = CMMCorePlus.instance()` line redundant and removable.
    
    However, if a specific core instance is required, you can create a core instance first and then pass it as the `mmcore` argument to the widget (if available, not all the widgets have it), like so: `GroupPresetTableWidget(mmcore=my_core)`.

You can add to this simple code any other widgets from this package to control and interact with the same [Micro-Manager core instance](https://pymmcore-plus.github.io/pymmcore-plus/api/cmmcoreplus/#pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance).

### Custom GUI

Creating a custom GUI with the widgets from this package requires a deeper understanding of the Qt environment, such as [PyQt6](https://pypi.org/project/PyQt6/). However, this documentation does not primarily focus on this aspect.

As shown in the video below, in this section, we only provide a simple example to illustrate the process of building a custom GUI using some of the `pymmcore-widgets`.

![type:video](./images/my_widget.mp4){: style='width: 100%'}

Here we create a [Qt Application](https://doc.qt.io/qt-6/qapplication.html) with a general-purpose [QWidget](https://doc.qt.io/qt-6/qwidget.html) that incorporates a variety of `pymmcore-widgets`: [ConfigurationWidget](./widgets/ConfigurationWidget/), [ChannelGroupWidget](./widgets/ChannelGroupWidget/), [ChannelWidget](./widgets/ChannelWidget/), [DefaultCameraExposureWidget](./widgets/DefaultCameraExposureWidget/), [ImagePreview](./widgets/ImagePreview/), [SnapButton](./widgets/SnapButton/), and [LiveButton](./widgets/LiveButton/).

This simple GUI can be used to load a `Micro-Manager` configuration file, snap an image or live stream images from the camera, with the flexibility to select a channel and adjust the exposure time.

```python title="custom_gui.py"
--8<-- "examples/custom_gui.py"
```

For a pre-made user interface, see [napari-micromanager](https://pypi.org/project/napari-micromanager/) ([github](https://github.com/pymmcore-plus/napari-micromanager)).
