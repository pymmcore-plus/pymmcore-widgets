from __future__ import annotations

import itertools
from collections import defaultdict
from itertools import cycle
from typing import (
    TYPE_CHECKING,
    Any,
    Hashable,
    Iterable,
    Literal,
    Mapping,
    Protocol,
)

import cmap
import numpy as np
import superqt
import useq
from psygnal import Signal as psygnalSignal
from pymmcore_plus.mda.handlers import OMEZarrWriter
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from superqt import QLabeledRangeSlider
from superqt.cmap import QColormapComboBox
from superqt.utils import signals_blocked

from ._dims_slider import DimsSliders
from ._vispy_canvas import VispyViewerCanvas

if TYPE_CHECKING:
    ImageKey = Hashable


CHANNEL = "c"
COLORMAPS = cycle(
    [cmap.Colormap("green"), cmap.Colormap("magenta"), cmap.Colormap("cyan")]
)


# FIXME: get rid of this thin subclass
class DataStore(OMEZarrWriter):
    frame_ready = psygnalSignal(object, useq.MDAEvent)

    def frameReady(self, frame: np.ndarray, event: useq.MDAEvent, meta: dict) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(frame, event)


class ChannelVisControl(QWidget):
    def __init__(
        self,
        name: str = "",
        handles: Iterable[PImageHandle] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._handles = handles
        self._name = name

        self._visible = QCheckBox(name)
        self._visible.setChecked(True)
        self._visible.toggled.connect(self._on_visible_changed)

        self._cmap = QColormapComboBox(allow_user_colormaps=True)
        self._cmap.currentColormapChanged.connect(self._on_cmap_changed)
        for color in ["green", "magenta", "cyan"]:
            self._cmap.addColormap(color)

        self.clims = QLabeledRangeSlider(Qt.Orientation.Horizontal)
        self.clims.setRange(0, 2**14)
        self.clims.valueChanged.connect(self._on_clims_changed)

        self._auto_clim = QCheckBox("Auto")
        self._auto_clim.toggled.connect(self.update_autoscale)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._visible)
        layout.addWidget(self._cmap)
        layout.addWidget(self.clims)
        layout.addWidget(self._auto_clim)

    def autoscaleChecked(self) -> bool:
        return self._auto_clim.isChecked()

    def _on_clims_changed(self, clims: tuple[float, float]) -> None:
        self._auto_clim.setChecked(False)
        for handle in self._handles:
            handle.clim = clims

    def _on_visible_changed(self, visible: bool) -> None:
        for handle in self._handles:
            handle.visible = visible

    def _on_cmap_changed(self, cmap: cmap.Colormap) -> None:
        for handle in self._handles:
            handle.cmap = cmap

    def update_autoscale(self) -> None:
        if not self._auto_clim.isChecked():
            return

        # find the min and max values for the current channel
        clims = [np.inf, -np.inf]
        for handle in self._handles:
            clims[0] = min(clims[0], np.nanmin(handle.data))
            clims[1] = max(clims[1], np.nanmax(handle.data))

        for handle in self._handles:
            handle.clim = clims

        # set the slider values to the new clims
        with signals_blocked(self.clims):
            self.clims.setValue(clims)


c = itertools.count()


class PDataStore(Protocol): ...


class PImageHandle(Protocol):
    @property
    def data(self) -> np.ndarray: ...
    @data.setter
    def data(self, data: np.ndarray) -> None: ...
    @property
    def visible(self) -> bool: ...
    @visible.setter
    def visible(self, visible: bool) -> None: ...
    @property
    def clim(self) -> Any: ...
    @clim.setter
    def clim(self, clims: tuple[float, float]) -> None: ...
    @property
    def cmap(self) -> Any: ...
    @cmap.setter
    def cmap(self, cmap: Any) -> None: ...


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

        self._channel_controls: dict[Hashable, ChannelVisControl] = {}
        for i, ch in enumerate(["DAPI", "FITC"]):
            self._channel_controls[i] = c = ChannelVisControl(ch, self._channels[i])
            layout.addWidget(c)

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
        if handles := self._channels.get(key):
            for handle in handles:
                handle.data = data
            if ctrl := self._channel_controls.get(key, None):
                ctrl.update_autoscale()
        else:
            cm = (
                next(COLORMAPS)
                if self._channel_mode == "composite"
                else cmap.Colormap("gray")
            )
            new_img = self._canvas.add_image(data, cmap=cm)
            self._channels[key].append(new_img)


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
