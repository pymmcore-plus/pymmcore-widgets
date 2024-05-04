from __future__ import annotations

from typing import TYPE_CHECKING

import superqt
import useq
from psygnal import Signal as psygnalSignal
from pymmcore_plus.mda.handlers import OMEZarrWriter

from ._stack_viewer import StackViewer

if TYPE_CHECKING:
    import numpy as np
    from qtpy.QtWidgets import QWidget


# FIXME: get rid of this thin subclass
class DataStore(OMEZarrWriter):
    frame_ready = psygnalSignal(object, useq.MDAEvent)

    def frameReady(self, frame: np.ndarray, event: useq.MDAEvent, meta: dict) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(frame, event)


class MDAViewer(StackViewer):
    """StackViewer specialized for pymmcore-plus MDA acquisitions."""

    def __init__(self, *, parent: QWidget | None = None):
        super().__init__(DataStore(), parent=parent, channel_axis="c")
        self._data.frame_ready.connect(self.on_frame_ready)
        self.dims_sliders.set_locks_visible(True)

    @superqt.ensure_main_thread  # type: ignore
    def on_frame_ready(self, frame: np.ndarray, event: useq.MDAEvent) -> None:
        self.setIndex(event.index)  # type: ignore
