# pymmcore-widgets

[![License](https://img.shields.io/pypi/l/pymmcore-widgets.svg?color=green)](https://github.com/fdrgsp/pymmcore-widgets/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/pymmcore-widgets.svg?color=green)](https://pypi.org/project/pymmcore-widgets)
[![Python Version](https://img.shields.io/pypi/pyversions/pymmcore-widgets.svg?color=green)](https://python.org)
[![CI](https://github.com/fdrgsp/pymmcore-widgets/actions/workflows/ci.yml/badge.svg)](https://github.com/fdrgsp/pymmcore-widgets/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/fdrgsp/pymmcore-widgets/branch/main/graph/badge.svg)](https://codecov.io/gh/fdrgsp/pymmcore-widgets)

A set of widgets for the [pymmcore-plus](https://github.com/pymmcore-plus/pymmcore-plus) package.
This package can be used to build custom user interfaces for micromanager in a python/Qt environment.

## Usage

```python
from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import StageWidget  # as an example... see below
from qtpy.QtWidgets import QApplication

core = CMMCorePlus.instance()
core.loadSystemConfiguration()

if __name__ == '__main__':
    app = QApplication([])
    stage = StageWidget('XY')
    stage.show()
    app.exec_()
```

![Screen Shot 2022-08-01 at 2 18 12 PM](https://user-images.githubusercontent.com/1609449/182217639-7f52a217-16f6-416a-a54f-2db63b7165c5.png)


Other existing widgets include (not exhaustive):

PropertyBrowser, GroupPresetTableWidget,
DefaultCameraExposureWidget, ConfigurationWidget, ChannelWidget,
ObjectivesWidget, SliderDialog, LiveButton, SnapButton, StageWidget


## Installation

```sh
pip install pymmcore-widgets
```
