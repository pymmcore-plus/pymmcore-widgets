from __future__ import annotations

import jax.numpy as jnp
from numpy_arr import generate_5d_sine_wave
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer_v2._stack_viewer import StackViewer

# Example usage
array_shape = (10, 3, 5, 512, 512)  # Specify the desired dimensions
sine_wave_5d = jnp.asarray(generate_5d_sine_wave(array_shape))

if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    v = StackViewer(sine_wave_5d, channel_axis=1)
    v.show()
    qapp.exec()
