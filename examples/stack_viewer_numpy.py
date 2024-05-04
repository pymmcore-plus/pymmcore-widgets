from __future__ import annotations

import numpy as np
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer2._stack_viewer import StackViewer


def generate_5d_sine_wave(
    shape: tuple[int, int, int, int, int],
    amplitude: float = 240,
    base_frequency: float = 5,
) -> np.ndarray:
    # Unpack the dimensions
    angle_dim, freq_dim, phase_dim, ny, nx = shape

    # Create an empty array to hold the data
    output = np.zeros(shape)

    # Define spatial coordinates for the last two dimensions
    half_per = base_frequency * np.pi
    x = np.linspace(-half_per, half_per, nx)
    y = np.linspace(-half_per, half_per, ny)
    y, x = np.meshgrid(y, x)

    # Iterate through each parameter in the higher dimensions
    for phase_idx in range(phase_dim):
        for freq_idx in range(freq_dim):
            for angle_idx in range(angle_dim):
                # Calculate phase and frequency
                phase = np.pi / phase_dim * phase_idx
                frequency = 1 + (freq_idx * 0.1)  # Increasing frequency with each step

                # Calculate angle
                angle = np.pi / angle_dim * angle_idx
                # Rotate x and y coordinates
                xr = np.cos(angle) * x - np.sin(angle) * y
                np.sin(angle) * x + np.cos(angle) * y

                # Compute the sine wave
                sine_wave = (amplitude * 0.5) * np.sin(frequency * xr + phase)
                sine_wave += amplitude * 0.5

                # Assign to the output array
                output[angle_idx, freq_idx, phase_idx] = sine_wave

    return output


# Example usage
array_shape = (10, 5, 5, 512, 512)  # Specify the desired dimensions
sine_wave_5d = generate_5d_sine_wave(array_shape)

if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    v = StackViewer(sine_wave_5d, channel_axis=2)
    v.show()
    qapp.exec()
