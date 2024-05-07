from __future__ import annotations

from typing import TYPE_CHECKING

from psygnal import Signal
from pymmcore_plus.mda.handlers._ome_zarr_writer import POS_PREFIX, OMEZarrWriter
from useq import MDAEvent

if TYPE_CHECKING:
    from typing import Any

    import numpy as np
    import useq


class QOMEZarrDatastore(OMEZarrWriter):
    frame_ready = Signal(MDAEvent)

    def __init__(self) -> None:
        super().__init__(store=None)

    def sequenceStarted(self, sequence: useq.MDASequence) -> None:
        self._used_axes = tuple(sequence.used_axes)
        super().sequenceStarted(sequence)

    def frameReady(
        self,
        frame: np.ndarray,
        event: useq.MDAEvent,
        meta: dict[Any, Any],
    ) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(event)

    def get_frame(self, event: MDAEvent) -> np.ndarray:
        key = f'{POS_PREFIX}{event.index.get("p", 0)}'
        ary = self.position_arrays[key]

        index = tuple(event.index.get(k) for k in self._used_axes)
        data: np.ndarray = ary[index]
        return data
