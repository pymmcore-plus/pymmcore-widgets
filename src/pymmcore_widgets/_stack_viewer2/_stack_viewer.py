from __future__ import annotations

import itertools
from collections import defaultdict
from itertools import cycle
from typing import TYPE_CHECKING, Hashable, Literal, Mapping, Protocol

import cmap
import superqt
import useq
from psygnal import Signal as psygnalSignal
from pymmcore_plus.mda.handlers import OMEZarrWriter
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from ._dims_slider import DimsSliders
from ._lut_control import LutControl, PImageHandle
from ._vispy_canvas import VispyViewerCanvas

if TYPE_CHECKING:
    import numpy as np


CHANNEL = "c"
GRAYS = cmap.Colormap("gray")
COLORMAPS = cycle(
    [cmap.Colormap("green"), cmap.Colormap("magenta"), cmap.Colormap("cyan")]
)


# FIXME: get rid of this thin subclass
class DataStore(OMEZarrWriter):
    frame_ready = psygnalSignal(object, useq.MDAEvent)

    def frameReady(self, frame: np.ndarray, event: useq.MDAEvent, meta: dict) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(frame, event)


c = itertools.count()


class PDataStore(Protocol): ...


class StackViewer(QWidget):
    """A viewer for MDA acquisitions started by MDASequence in pymmcore-plus events."""

    def __init__(self, datastore: PDataStore, *, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self._channels: defaultdict[Hashable, list[PImageHandle]] = defaultdict(list)

        self.datastore = datastore
        self._canvas = VispyViewerCanvas()
        self._info_bar = QLabel("Info")
        self._dims_sliders = DimsSliders()
        self.set_channel_mode("composite")

        self._canvas.infoText.connect(lambda x: self._info_bar.setText(x))
        self._dims_sliders.valueChanged.connect(self._on_dims_sliders_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._dims_sliders)

        self._channel_controls: dict[Hashable, LutControl] = {}

    def set_channel_mode(self, mode: Literal["composite", "grayscale"]) -> None:
        if mode == getattr(self, "_channel_mode", None):
            return

        self._channel_mode = mode
        if mode == "composite":
            self._dims_sliders.set_dimension_visible(CHANNEL, False)
        else:
            self._dims_sliders.set_dimension_visible(CHANNEL, True)

    def _image_key(self, index: Mapping[str, int]) -> Hashable:
        if self._channel_mode == "composite":
            return index.get("c", 0)
        return 0

    def _isel(self, index: dict) -> np.ndarray:
        return isel(self.datastore, index)

    def _on_dims_sliders_changed(self, index: dict) -> None:
        """Set the current image index."""
        c = index.get(CHANNEL, 0)
        indices = [index]
        if self._channel_mode == "composite":
            for i, handles in self._channels.items():
                if handles and c != i:
                    indices.append({**index, CHANNEL: i})

        for idx in indices:
            self._update_data_for_index(idx)
        self._canvas.refresh()

    def _update_data_for_index(self, index: dict) -> None:
        key = self._image_key(index)
        data = self._isel(index)
        if handles := self._channels[key]:
            for handle in handles:
                handle.data = data
            if ctrl := self._channel_controls.get(key, None):
                ctrl.update_autoscale()
        else:
            cm = next(COLORMAPS) if self._channel_mode == "composite" else GRAYS
            handles.append(self._canvas.add_image(data, cmap=cm))
            if key not in self._channel_controls:
                channel_name = f"Channel {key}"
                self._channel_controls[key] = c = LutControl(channel_name, handles)
                self.layout().addWidget(c)


class MDAViewer(StackViewer):
    def __init__(self, *, parent: QWidget | None = None):
        # self._core = CMMCorePlus.instance()
        # self._core.mda.events.frameReady.connect(self.on_frame_ready)
        super().__init__(DataStore(), parent=parent)
        self.datastore.frame_ready.connect(self.on_frame_ready)

    @superqt.ensure_main_thread
    def on_frame_ready(self, frame: np.ndarray, event: useq.MDAEvent) -> None:
        self._dims_sliders.setValue(event.index)


def isel(writer: OMEZarrWriter, indexers: Mapping[str, int | slice]) -> np.ndarray:
    p_index = indexers.get("p", 0)
    if isinstance(p_index, slice):
        raise NotImplementedError("Cannot slice over position index")  # TODO

    try:
        sizes = [*list(writer.position_sizes[p_index]), "y", "x"]
    except IndexError as e:
        raise IndexError(
            f"Position index {p_index} out of range for {len(writer.position_sizes)}"
        ) from e

    data = writer.position_arrays[writer.get_position_key(p_index)]
    full = slice(None, None)
    index = tuple(indexers.get(k, full) for k in sizes)
    return data[index]  # type: ignore
