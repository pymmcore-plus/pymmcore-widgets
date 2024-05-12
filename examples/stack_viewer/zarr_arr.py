from __future__ import annotations

import zarr
import zarr.storage
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer_v2 import StackViewer

URL = "https://s3.embl.de/i2k-2020/ngff-example-data/v0.4/tczyx.ome.zarr"
zarr_arr = zarr.open(URL, mode="r")

if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    v = StackViewer(zarr_arr["s0"])
    v.show()
    qapp.exec()
