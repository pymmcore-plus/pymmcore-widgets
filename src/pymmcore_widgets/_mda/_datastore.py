from __future__ import annotations

import numpy as np
from pymmcore_plus.mda.handlers._ome_zarr_writer import OMEZarrWriter, POS_PREFIX
from psygnal import Signal
from useq import MDAEvent

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import useq


class QOMEZarrDatastore(OMEZarrWriter):
    frame_ready = Signal(MDAEvent)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, store=None, **kwargs)

    def frameReady(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: dict | None = None
    ) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(event)
        print("FRAME IN LOCAL DATASTORE")

    def get_frame(self, event) -> np.ndarray:
        key = f'{POS_PREFIX}{event.index.get("p", 0)}'
        ary = self._arrays[key]
        index = tuple(event.index.get(k) for k in self._used_axes)
        return ary[index]
