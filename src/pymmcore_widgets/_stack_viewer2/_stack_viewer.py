from __future__ import annotations

from collections import defaultdict
from itertools import cycle
from typing import TYPE_CHECKING, Any, Hashable, Literal, Mapping, cast

import cmap
import numpy as np
import superqt
import useq
from psygnal import Signal as psygnalSignal
from pymmcore_plus.mda.handlers import OMETiffWriter, OMEZarrWriter
from qtpy.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ._dims_slider import DimsSliders
from ._lut_control import LutControl

# from ._pygfx_canvas import PyGFXViewerCanvas
from ._vispy_canvas import VispyViewerCanvas

if TYPE_CHECKING:
    from ._protocols import PCanvas, PImageHandle

    ColorMode = Literal["composite", "grayscale"]

GRAYS = cmap.Colormap("gray")
COLORMAPS = [cmap.Colormap("green"), cmap.Colormap("magenta"), cmap.Colormap("cyan")]


# FIXME: get rid of this thin subclass
class DataStore(OMEZarrWriter):
    frame_ready = psygnalSignal(object, useq.MDAEvent)

    def frameReady(self, frame: np.ndarray, event: useq.MDAEvent, meta: dict) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(frame, event)


class ColorModeButton(QPushButton):
    def __init__(self, parent: QWidget | None = None):
        modes = ["composite", "grayscale"]
        self._modes = cycle(modes)
        super().__init__(modes[-1], parent)
        self.clicked.connect(self.next_mode)
        self.next_mode()

    def next_mode(self) -> None:
        self._mode = self.text()
        self.setText(next(self._modes))

    def mode(self) -> ColorMode:
        return self._mode  # type: ignore


class StackViewer(QWidget):
    """A viewer for MDA acquisitions started by MDASequence in pymmcore-plus events."""

    def __init__(
        self,
        data: Any,
        *,
        parent: QWidget | None = None,
        channel_axis: int | str = 0,
    ):
        super().__init__(parent=parent)

        self._channels: defaultdict[Hashable, list[PImageHandle]] = defaultdict(list)
        self._channel_controls: dict[Hashable, LutControl] = {}

        self._sizes = {}
        self.set_data(data)
        self._channel_axis = channel_axis

        self._info_bar = QLabel("Info")
        self._canvas: PCanvas = VispyViewerCanvas(self._info_bar.setText)
        # self._canvas: PCanvas = PyGFXViewerCanvas(self._info_bar.setText)
        self._dims_sliders = DimsSliders()
        self._cmaps = cycle(COLORMAPS)
        self.set_channel_mode("grayscale")

        self._dims_sliders.valueChanged.connect(self._on_dims_sliders_changed)

        self._channel_mode_picker = ColorModeButton()
        self._channel_mode_picker.clicked.connect(self.set_channel_mode)
        self._set_range_btn = QPushButton("reset zoom")
        self._set_range_btn.clicked.connect(self._set_range_clicked)

        btns = QHBoxLayout()
        btns.addWidget(self._channel_mode_picker)
        btns.addWidget(self._set_range_btn)
        layout = QVBoxLayout(self)
        layout.addLayout(btns)
        layout.addWidget(self._canvas.qwidget(), 1)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._dims_sliders)

    def set_data(self, data: Any, sizes: Mapping | None = None) -> None:
        if sizes is not None:
            self._sizes = dict(sizes)
        else:
            if (sz := getattr(data, "sizes", None)) and isinstance(sz, Mapping):
                self._sizes = sz
            elif (shp := getattr(data, "shape", None)) and isinstance(shp, tuple):
                self._sizes = {k: v - 1 for k, v in enumerate(shp[:-2])}
            else:
                self._sizes = {}
        self._datastore = data

    @property
    def sizes(self) -> Mapping[Hashable, int]:
        return self._sizes

    def update_slider_maxima(
        self, sizes: Any | tuple[int, ...] | Mapping[Hashable, int] | None = None
    ) -> None:
        if sizes is None:
            _sizes = self.sizes
        elif isinstance(sizes, tuple):
            _sizes = {k: v - 1 for k, v in enumerate(sizes[:-2])}
        elif not isinstance(sizes, Mapping):
            raise ValueError(f"Invalid shape {sizes}")
        self._dims_sliders.setMaximum(_sizes)

    def _set_range_clicked(self) -> None:
        self._canvas.set_range()

    def set_channel_mode(self, mode: ColorMode | None = None) -> None:
        if mode is None or isinstance(mode, bool):
            mode = self._channel_mode_picker.mode()
        if mode == getattr(self, "_channel_mode", None):
            return

        self._cmaps = cycle(COLORMAPS)
        self._channel_mode = mode
        c_visible = mode != "composite"
        self._dims_sliders.set_dimension_visible(self._channel_axis, c_visible)
        num_channels = self._dims_sliders.maximum().get(self._channel_axis, -1) + 1
        value = self._dims_sliders.value()
        if self._channels:
            for handles in self._channels.values():
                for handle in handles:
                    handle.remove()
            self._channels.clear()
            for c in self._channel_controls.values():
                cast("QVBoxLayout", self.layout()).removeWidget(c)
                c.deleteLater()
            self._channel_controls.clear()
            if c_visible:
                self._update_data_for_index(value)
            else:
                for i in range(num_channels):
                    self._update_data_for_index({**value, self._channel_axis: i})
        self._canvas.refresh()

    def _image_key(self, index: Mapping[str, int]) -> Hashable:
        if self._channel_mode == "composite":
            return index.get("c", 0)
        return 0

    def _isel(self, index: Mapping) -> np.ndarray:
        return isel(self._datastore, index)

    def _on_dims_sliders_changed(self, index: dict) -> None:
        """Set the current image index."""
        c = index.get(self._channel_axis, 0)
        indices = [index]
        if self._channel_mode == "composite":
            for i, handles in self._channels.items():
                if handles and c != i:
                    indices.append({**index, self._channel_axis: i})

        for idx in indices:
            self._update_data_for_index(idx)
        self._canvas.refresh()

    def _update_data_for_index(self, index: Mapping) -> None:
        key = self._image_key(index)
        data = self._isel(index)
        if handles := self._channels[key]:
            for handle in handles:
                handle.data = data
            if ctrl := self._channel_controls.get(key, None):
                ctrl.update_autoscale()
        else:
            cm = next(self._cmaps) if self._channel_mode == "composite" else GRAYS
            handles.append(self._canvas.add_image(data, cmap=cm))
            if key not in self._channel_controls:
                channel_name = f"Channel {key}"
                self._channel_controls[key] = c = LutControl(channel_name, handles)
                cast("QVBoxLayout", self.layout()).addWidget(c)

    def setIndex(self, index: Mapping[str, int]) -> None:
        self._dims_sliders.setValue(index)


class MDAViewer(StackViewer):
    def __init__(self, *, parent: QWidget | None = None):
        super().__init__(DataStore(), parent=parent, channel_axis="c")
        self._datastore.frame_ready.connect(self.on_frame_ready)

    @superqt.ensure_main_thread
    def on_frame_ready(self, frame: np.ndarray, event: useq.MDAEvent) -> None:
        self.setIndex(event.index)


def isel(store: Any, indexers: Mapping[str, int | slice]) -> np.ndarray:
    if isinstance(store, (OMEZarrWriter, OMETiffWriter)):
        return isel_mmcore_5dbase(store, indexers)
    if isinstance(store, np.ndarray):
        return isel_np_array(store, indexers)
    raise NotImplementedError(f"Unknown datastore type {type(store)}")


def isel_np_array(data: np.ndarray, indexers: Mapping[str, int | slice]) -> np.ndarray:
    idx = tuple(indexers.get(k, slice(None)) for k in range(data.ndim))
    return data[idx]


def isel_mmcore_5dbase(
    writer: OMEZarrWriter | OMETiffWriter, indexers: Mapping[str, int | slice]
) -> np.ndarray:
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
