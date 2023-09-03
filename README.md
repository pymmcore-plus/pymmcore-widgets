# pymmcore-widgets

[![License](https://img.shields.io/pypi/l/pymmcore-widgets.svg?color=green)](https://github.com/pymmcore-plus/pymmcore-widgets/raw/main/LICENSE)
[![Python Version](https://img.shields.io/pypi/pyversions/pymmcore-widgets.svg?color=green)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/pymmcore-widgets.svg?color=green)](https://pypi.org/project/pymmcore-widgets)
[![Conda](https://img.shields.io/conda/vn/conda-forge/pymmcore-widgets)](https://anaconda.org/conda-forge/pymmcore-widgets)
[![CI](https://github.com/pymmcore-plus/pymmcore-widgets/actions/workflows/ci.yml/badge.svg)](https://github.com/pymmcore-plus/pymmcore-widgets/actions/workflows/ci.yml)
[![docs](https://github.com/pymmcore-plus/pymmcore-plus/actions/workflows/docs.yml/badge.svg)](https://pymmcore-plus.github.io/pymmcore-widgets/)
[![codecov](https://codecov.io/gh/pymmcore-plus/pymmcore-widgets/branch/main/graph/badge.svg)](https://codecov.io/gh/pymmcore-plus/pymmcore-widgets)

A set of widgets for the [pymmcore-plus](https://github.com/pymmcore-plus/pymmcore-plus) package.
This package can be used to build custom user interfaces for micromanager in a python/Qt environment.
It forms the basis of [`napari-micromanager`](https://github.com/pymmcore-plus/napari-micromanager)

### [:book: Documentation](https://pymmcore-plus.github.io/pymmcore-widgets)

<img width="1721" alt="mm_widgets" src="https://github.com/pymmcore-plus/pymmcore-widgets/assets/1609449/20747052-8621-4c6d-a9ab-473792b411ac">

See complete list of available widgets in the [documentation](https://pymmcore-plus.github.io/pymmcore-widgets/#widgets)


## Installation

```sh
pip install pymmcore-widgets

# note that this package does NOT include a Qt backend
# you must install one yourself, for example:
pip install PyQt5

# package is tested against PyQt5, PyQt6, PySide2, and PySide6
```
