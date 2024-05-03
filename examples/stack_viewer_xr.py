from __future__ import annotations

# from stack_viewer_numpy import generate_5d_sine_wave
import nd2
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer2._stack_viewer import StackViewer

# array_shape = (10, 5, 3, 512, 512)  # Specify the desired dimensions
# sine_wave_5d = generate_5d_sine_wave(array_shape)
# data = xr.DataArray(sine_wave_5d, dims=["a", "f", "p", "y", "x"])

data = and2.imread("~/dev/self/nd2/tests/data/t3p3z5c3.and2", xarray=True)
qapp = QtWidgets.QApplication([])
v = StackViewer(data, channel_axis="C")
v.show()
v.update_slider_maxima()
v.setIndex({})
qapp.exec()
