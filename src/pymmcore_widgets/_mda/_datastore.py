from __future__ import annotations

from typing import TYPE_CHECKING

from psygnal import Signal
from pymmcore_plus.mda.handlers._ome_zarr_writer import POS_PREFIX, OMEZarrWriter
from useq import MDAEvent

if TYPE_CHECKING:
    import numpy as np
    import useq


class QOMEZarrDatastore(OMEZarrWriter):
    frame_ready = Signal(MDAEvent)

    def __init__(self) -> None:
        super().__init__(store=None)

    def frameReady(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: dict | None = None
    ) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(event)

    def get_frame(self, event: MDAEvent) -> np.ndarray:
        key = f'{POS_PREFIX}{event.index.get("p", 0)}'
        ary = self._arrays[key]
        index = tuple(event.index.get(k) for k in self._used_axes)
        data: np.ndarray = ary[index]
        return data
