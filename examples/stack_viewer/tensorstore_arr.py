from __future__ import annotations

import numpy as np
import tensorstore as ts
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer_v2 import StackViewer

shape = (10, 4, 3, 512, 512)
ts_array = ts.open(
    {"driver": "zarr", "kvstore": {"driver": "memory"}},
    create=True,
    shape=shape,
    dtype=ts.uint8,
).result()
ts_array[:] = np.random.randint(0, 255, size=shape, dtype=np.uint8)

if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    v = StackViewer(ts_array)
    v.show()
    qapp.exec()
