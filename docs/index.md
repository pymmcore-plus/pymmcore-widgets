# Overview

[pymmcore-widgets](https://pypi.org/project/pymmcore-widgets/) is a library of
[PyQt](https://riverbankcomputing.com/software/pyqt/)/[PySide](https://www.qt.io/qt-for-python)
widgets that can be used in combination with
[pymmcore-plus](https://pymmcore-plus.github.io/pymmcore-plus)
([github](https://github.com/pymmcore-plus/pymmcore-plus)) to create custom graphical user
interfaces to control [Micro-Manager](https://micro-manager.org) in a python/C++ environment.

## Installation

```sh
pip install pymmcore-widgets
```

!!! Important
    This package does **NOT** include a [PyQt](https://riverbankcomputing.com/software/pyqt/)/[PySide](https://www.qt.io/qt-for-python) backend, you must install one yourself (e.g. ```pip install PyQt6```).

!!! Note
    Widgets are tested on:

    * `macOS & Windows`
    * `Python 3.8, 3.9 & 3.10`
    * `PyQt5 & PyQt6`
    * `PySide2 & PySide6`

For a more detailed description on how to install the package, see the [Getting Started](getting_started.md) section.

## Usage

For a pre-made user interface, see [napari-micromanager](https://pypi.org/project/napari-micromanager/) ([github](https://github.com/pymmcore-plus/napari-micromanager)).

A more detailed description on how to use the Widgets explained in the [Getting Started](getting_started.md) section.


## Widgets List

Below there is a list of all the widgets available in this package. They are **grouped by their functionality**.
More detailed information on each widget can be found in the [Getting Started](getting_started.md) section as well as in the individual widget documentation.


### Multi-Dimensional Acquisition (MDA) Widgets

The widgets in this section can be used to **setup (and run) a multi-dimensional acquisition** based on the [useq-schema MDASequence](https://pymmcore-plus.github.io/useq-schema/schema/sequence/#useq.MDASequence).

{{ MDA_WIDGET_TABLE }}


### Devices and Properties Widgets

The widgets in this section can be used to **control and intract with the devices and properties** of a Micro-Manager core [(CMMCorePlus)](https://pymmcore-plus.github.io/pymmcore-plus/api/cmmcoreplus/#cmmcoreplus).

{{ DEV_PROP_WIDGET_TABLE }}


### Configurations Widgets

The widgets in this section can be used to **create, load and modify** a Micro-Manager configuration file.

{{ CFG_WIDGET_TABLE }}


### Misc Widgets

{{ MISC_WIDGET_TABLE }}
