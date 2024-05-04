from __future__ import annotations

# from stack_viewer_numpy import generate_5d_sine_wave
import and2
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer2._stack_viewer import StackViewer

data = and2.imread("/Users/talley/Downloads/6D_test.nd2", xarray=True, dask=True)
qapp = QtWidgets.QApplication([])
v = StackViewer(data, channel_axis="C")
v.show()
qapp.exec()
