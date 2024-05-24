from __future__ import annotations

import xarray as xr
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer_v2 import StackViewer

da = xr.tutorial.open_dataset("air_temperature").air

if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    v = StackViewer(da, colormaps=["thermal"], channel_mode="composite")
    v.show()
    qapp.exec()
