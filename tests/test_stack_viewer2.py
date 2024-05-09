from __future__ import annotations

import dask.array as da
import numpy as np
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer_v2 import StackViewer


def make_lazy_array(shape: tuple[int, ...]) -> da.Array:
    rest_shape = shape[:-2]
    frame_shape = shape[-2:]

    def _dask_block(block_id: tuple[int, int, int, int, int]) -> np.ndarray | None:
        if isinstance(block_id, np.ndarray):
            return None
        size = (1,) * len(rest_shape) + frame_shape
        return np.random.randint(0, 255, size=size, dtype=np.uint8)

    chunks = [(1,) * x for x in rest_shape] + [(x,) for x in frame_shape]
    return da.map_blocks(_dask_block, chunks=chunks, dtype=np.uint8)  # type: ignore


if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    dask_arr = make_lazy_array((1000, 64, 3, 256, 256))
    v = StackViewer(dask_arr)
    v.show()
    qapp.exec()
