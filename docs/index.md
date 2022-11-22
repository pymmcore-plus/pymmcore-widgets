# Overview

[pymmcore-widgets](https://pypi.org/project/pymmcore-widgets/) is a library of
[PyQt](https://riverbankcomputing.com/software/pyqt/)/[PySide](https://www.qt.io/qt-for-python)
widgets that can be used in combination with
[pymmcore-plus](https://pymmcore-plus.github.io/pymmcore-plus)
([github](https://github.com/pymmcore-plus/pymmcore-plus)) to build custom user
interfaces for [Micro-Manager](https://micro-manager.org) in a python/C++
environment.

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

{{ WIDGET_TABLE }}

## Usage

For a pre-made user interface, see [napari-micromanager](https://pypi.org/project/napari-micromanager/) ([github](https://github.com/pymmcore-plus/napari-micromanager)).

Detailed description and usage of each Widget is explained in their [respective pages](#widgets).
