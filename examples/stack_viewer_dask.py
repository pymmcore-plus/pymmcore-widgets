from __future__ import annotations

import numpy as np
from dask.array.core import map_blocks
from qtpy import QtWidgets

from pymmcore_widgets._stack_viewer._stack_viewer import StackViewer


def _dask_block(block_id: tuple[int, int, int, int, int]) -> np.ndarray | None:
    if isinstance(block_id, np.ndarray):
        return None
    data = np.random.randint(0, 255, size=(1000, 1000), dtype=np.uint8)
    return data[(None,) * 3]


shape = (1000, 64, 3, 512, 512)
chunks = [(1,) * x for x in shape[:-2]]
chunks += [(x,) for x in shape[-2:]]
dask_arr = map_blocks(_dask_block, chunks=chunks, dtype=np.uint8)

if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    v = StackViewer(dask_arr)
    v.show()
    qapp.exec()
