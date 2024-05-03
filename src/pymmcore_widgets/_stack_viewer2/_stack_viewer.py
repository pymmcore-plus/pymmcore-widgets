from __future__ import annotations

from collections import defaultdict
from itertools import cycle
from typing import TYPE_CHECKING, Any, Hashable, Iterable, Literal, Mapping, cast

import cmap
from qtpy.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ._canvas._vispy import VispyViewerCanvas
from ._dims_slider import DimsSliders
from ._indexing import isel
from ._lut_control import LutControl

if TYPE_CHECKING:
    import numpy as np

    from ._dims_slider import DimensionKey, Indices, Sizes
    from ._protocols import PCanvas, PImageHandle

    ColorMode = Literal["composite", "grayscale"]


GRAYS = cmap.Colormap("gray")
COLORMAPS = [cmap.Colormap("green"), cmap.Colormap("magenta"), cmap.Colormap("cyan")]


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
        channel_axis: DimensionKey = 0,
    ):
        super().__init__(parent=parent)

        self._channels: defaultdict[DimensionKey, list[PImageHandle]] = defaultdict(
            list
        )
        self._channel_controls: dict[DimensionKey, LutControl] = {}

        self._sizes: Sizes = {}
        # the set of dimensions we are currently visualizing (e.g. XY)
        self._visible_dims: set[DimensionKey] = set()

        self._channel_axis = channel_axis

        self._info_bar = QLabel("Info")
        self._canvas: PCanvas = VispyViewerCanvas(self._info_bar.setText)
        # self._canvas: PCanvas = QtViewerCanvas(self._info_bar.setText)
        # self._canvas: PCanvas = PyGFXViewerCanvas(self._info_bar.setText)
        self._dims_sliders = DimsSliders()
        self._cmaps = cycle(COLORMAPS)
        self.set_channel_mode("grayscale")

        self._dims_sliders.valueChanged.connect(self._on_dims_sliders_changed)

        self._channel_mode_picker = ColorModeButton()
        self._channel_mode_picker.clicked.connect(self.set_channel_mode)
        self._set_range_btn = QPushButton("reset zoom")
        self._set_range_btn.clicked.connect(self._set_range_clicked)

        self.set_data(data)

        btns = QHBoxLayout()
        btns.addWidget(self._channel_mode_picker)
        btns.addWidget(self._set_range_btn)
        layout = QVBoxLayout(self)
        layout.addLayout(btns)
        layout.addWidget(self._canvas.qwidget(), 1)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._dims_sliders)

    def set_data(self, data: Any, sizes: Sizes | None = None) -> None:
        if sizes is not None:
            self._sizes = dict(sizes)
        else:
            if (sz := getattr(data, "sizes", None)) and isinstance(sz, Mapping):
                self._sizes = sz
            elif (shp := getattr(data, "shape", None)) and isinstance(shp, tuple):
                self._sizes = dict(enumerate(shp[:-2]))
            else:
                self._sizes = {}

        self._datastore = data
        self.set_visible_dims(list(self._sizes)[-2:])

    def set_visible_dims(self, dims: Iterable[DimensionKey]) -> None:
        self._visible_dims = set(dims)
        for d in self._visible_dims:
            self._dims_sliders.set_dimension_visible(d, False)

    @property
    def sizes(self) -> Sizes:
        return self._sizes

    def update_slider_maxima(
        self, sizes: tuple[int, ...] | Sizes | None = None
    ) -> None:
        if sizes is None:
            _sizes = self.sizes
        elif isinstance(sizes, tuple):
            _sizes = dict(enumerate(sizes[:-2]))
        elif not isinstance(sizes, Mapping):
            raise ValueError(f"Invalid shape {sizes}")

        for dim in list(_sizes.values())[-2:]:
            self._dims_sliders.set_dimension_visible(dim, False)
        self._dims_sliders.setMaximum({k: v - 1 for k, v in _sizes.items()})

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

    def _image_key(self, index: Indices) -> Hashable:
        if self._channel_mode == "composite":
            val = index.get(self._channel_axis, 0)
            if isinstance(val, slice):
                return (val.start, val.stop)
            return val
        return 0

    def _isel(self, index: Indices) -> np.ndarray:
        idx = {k: v for k, v in index.items() if k not in self._visible_dims}
        try:
            return isel(self._datastore, idx)
        except Exception as e:
            raise type(e)(f"Failed to index data with {idx}: {e}") from e

    def _on_dims_sliders_changed(self, index: Indices) -> None:
        """Set the current image index."""
        c = index.get(self._channel_axis, 0)
        indices: list[Indices] = [index]
        if self._channel_mode == "composite":
            for i, handles in self._channels.items():
                if handles and c != i:
                    # FIXME: type error is legit
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

    def setIndex(self, index: Indices) -> None:
        self._dims_sliders.setValue(index)
