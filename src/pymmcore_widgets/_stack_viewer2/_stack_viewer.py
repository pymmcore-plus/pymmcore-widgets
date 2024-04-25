from __future__ import annotations

from contextlib import suppress
import itertools
import logging
from itertools import cycle
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping, cast
from warnings import warn

import cmap
import numpy as np
import superqt
import useq
from psygnal import Signal as psygnalSignal
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import OMEZarrWriter
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledRangeSlider, QLabeledSlider
from superqt.cmap import QColormapComboBox
from superqt.iconify import QIconifyIcon
from vispy import scene

if TYPE_CHECKING:
    import numpy.typing as npt
    from PySide6.QtCore import QTimerEvent
    from vispy.scene.events import SceneMouseEvent

    ImageKey = tuple[tuple[str, int], ...]


CHANNEL = "c"
COLORMAPS = cycle(
    [cmap.Colormap("green"), cmap.Colormap("magenta"), cmap.Colormap("cyan")]
)


# FIXME: get rid of this thin subclass
class DataStore(OMEZarrWriter):
    frame_ready = psygnalSignal(useq.MDAEvent)

    def frameReady(self, frame: np.ndarray, event: useq.MDAEvent, meta: dict) -> None:
        super().frameReady(frame, event, meta)
        self.frame_ready.emit(event)


class PlayButton(QPushButton):
    """Just a styled QPushButton that toggles between play and pause icons."""

    PLAY_ICON = "fa6-solid:play"
    PAUSE_ICON = "fa6-solid:pause"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        icn = QIconifyIcon(self.PLAY_ICON)
        icn.addKey(self.PAUSE_ICON, state=QIconifyIcon.State.On)
        super().__init__(icn, text, parent)
        self.setCheckable(True)


class LockButton(QPushButton):
    LOCK_ICON = "fa6-solid:lock-open"
    UNLOCK_ICON = "fa6-solid:lock"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        icn = QIconifyIcon(self.LOCK_ICON)
        icn.addKey(self.UNLOCK_ICON, state=QIconifyIcon.State.On)
        super().__init__(icn, text, parent)
        self.setCheckable(True)
        self.setMaximumWidth(20)


class ChannelVisControl(QWidget):
    visibilityChanged = Signal(bool)
    climsChanged = Signal(tuple)
    cmapChanged = Signal(cmap.Colormap)

    def __init__(self, idx: int, name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.idx = idx
        self._name = name

        self._visible = QCheckBox(name)
        self._visible.setChecked(True)
        self._visible.toggled.connect(self.visibilityChanged)

        self._cmap = QColormapComboBox(allow_user_colormaps=True)
        self._cmap.currentColormapChanged.connect(self.cmapChanged)
        for color in ["green", "magenta", "cyan"]:
            self._cmap.addColormap(color)

        self._clims = QLabeledRangeSlider(Qt.Orientation.Horizontal)
        self._clims.setRange(0, 2**14)
        self._clims.valueChanged.connect(self.climsChanged)

        self._auto_clim = QCheckBox("Auto")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._visible)
        layout.addWidget(self._cmap)
        layout.addWidget(self._clims)
        layout.addWidget(self._auto_clim)

    def set_clim_for_dtype(self, dtype: npt.DTypeLike) -> None:
        # get maximum possible value for the dtype
        self._clims.setRange(0, np.iinfo(dtype).max)


class DimsSlider(QWidget):
    """A single slider in the DimsSliders widget.

    Provides a play/pause button that toggles animation of the slider value.
    Has a QLabeledSlider for the actual value.
    Adds a label for the maximum value (e.g. "3 / 10")
    """

    valueChanged = Signal(str, int)

    def __init__(self, dimension_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._interval = 1000 // 10
        self._name = dimension_name

        self._play_btn = PlayButton(dimension_name)
        self._play_btn.toggled.connect(self._toggle_animation)
        # note, this lock button only prevents the slider from updating programmatically
        # using self.setValue, it doesn't prevent the user from changing the value.
        self._lock_btn = LockButton()

        self._max_label = QLabel("/ 0")
        self._slider = QLabeledSlider(Qt.Orientation.Horizontal, parent=self)
        self._slider.setMaximum(0)
        self._slider.rangeChanged.connect(self._on_range_changed)
        self._slider.valueChanged.connect(self._on_value_changed)
        self._slider.layout().addWidget(self._max_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._play_btn)
        layout.addWidget(self._slider)
        layout.addWidget(self._lock_btn)

    def setMaximum(self, max_val: int) -> None:
        self._slider.setMaximum(max_val)

    def setValue(self, val: int) -> None:
        # variant of setValue that always updates the maximum
        if val > self._slider.maximum():
            self._slider.setMaximum(val)
        if self._lock_btn.isChecked():
            return
        self._slider.setValue(val)

    def set_fps(self, fps: int) -> None:
        self._interval = 1000 // fps

    def _toggle_animation(self, checked: bool) -> None:
        if checked:
            self._timer_id = self.startTimer(self._interval)
        else:
            self.killTimer(self._timer_id)

    def timerEvent(self, event: QTimerEvent) -> None:
        val = self._slider.value()
        next_val = (val + 1) % (self._slider.maximum() + 1)
        self._slider.setValue(next_val)

    def _on_range_changed(self, min: int, max: int) -> None:
        self._max_label.setText("/ " + str(max))

    def _on_value_changed(self, value: int) -> None:
        self.valueChanged.emit(self._name, value)


class DimsSliders(QWidget):
    """A Collection of DimsSlider widgets for each dimension in the data.

    Maintains the global current index and emits a signal when it changes.
    """

    indexChanged = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sliders: dict[str, DimsSlider] = {}
        self._current_index: dict[str, int] = {}
        self._invisible_dims: set[str] = set()
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def add_dimension(self, name: str) -> None:
        self._sliders[name] = slider = DimsSlider(dimension_name=name, parent=self)
        self._current_index[name] = 0
        slider.valueChanged.connect(self._on_value_changed)
        self.layout().addWidget(slider)
        slider.setVisible(name not in self._invisible_dims)

    def set_dimension_visible(self, name: str, visible: bool) -> None:
        if visible:
            self._invisible_dims.discard(name)
        else:
            self._invisible_dims.add(name)
        if name in self._sliders:
            self._sliders[name].setVisible(visible)

    def remove_dimension(self, name: str) -> None:
        try:
            slider = self._sliders.pop(name)
        except KeyError:
            warn(f"Dimension {name} not found in DimsSliders", stacklevel=2)
            return
        self.layout().removeWidget(slider)
        slider.deleteLater()

    def _on_value_changed(self, dim_name: str, value: int) -> None:
        self._current_index[dim_name] = value
        if not self._updating:
            self.indexChanged.emit(self._current_index)

    def add_or_update_dimension(self, name: str, value: int) -> None:
        if name in self._sliders:
            self._sliders[name].setValue(value)
        else:
            self.add_dimension(name)

    def update_dimensions(self, index: Mapping[str, int]) -> None:
        prev = self._current_index.copy()
        self._updating = True
        try:
            for dim, value in index.items():
                self.add_or_update_dimension(dim, value)
            if self._current_index != prev:
                self.indexChanged.emit(self._current_index)
        finally:
            self._updating = False


class VispyViewerCanvas(QWidget):
    """Vispy-based viewer for data.

    All vispy-specific code is encapsulated in this class (and non-vispy canvases
    could be swapped in if needed as long as they implement the same interface).
    """

    infoText = Signal(str)

    def __init__(
        self,
        datastore: OMEZarrWriter,
        channel_mode: str = "composite",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._datastore = datastore

        self._channel_mode = channel_mode
        self._canvas = scene.SceneCanvas(parent=self)
        self._canvas.events.mouse_move.connect(self._on_mouse_move)
        self._camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        central_wdg: scene.Widget = self._canvas.central_widget
        self._view: scene.ViewBox = central_wdg.add_view(camera=self._camera)

        # Mapping of image key to Image visual objects
        # tbd... determine what the key should be
        # could have an image per channel,
        # but may also have multiple images per channel... in the case of tiles, etc...
        self._images: dict[ImageKey, scene.visuals.Image] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas.native)

    def _on_mouse_move(self, event: SceneMouseEvent) -> None:
        """Mouse moved on the canvas, display the pixel value and position."""
        images = []
        # Get the images the mouse is over
        seen = set()
        while visual := self._canvas.visual_at(event.pos):
            if isinstance(visual, scene.visuals.Image):
                images.append(visual)
            visual.interactive = False
            seen.add(visual)
        for visual in seen:
            visual.interactive = True
        if not images:
            return

        tform = images[0].get_transform("canvas", "visual")
        px, py, *_ = (int(x) for x in tform.map(event.pos))
        text = f"[{py}, {px}]"
        for c, img in enumerate(images):
            with suppress(IndexError):
                text += f" c{c}: {img._data[py, px]}"
        self.infoText.emit(text)

    def add_image(self, key: ImageKey, data: np.ndarray | None = None) -> None:
        """Add a new Image node to the scene."""
        if self._channel_mode == "composite":
            cmap = next(COLORMAPS).to_vispy()
        else:
            cmap = "grays"

        self._images[key] = img = scene.visuals.Image(
            data, cmap=cmap, parent=self._view.scene
        )
        img.set_gl_state("additive", depth_test=False)
        self.set_range()
        img.interactive = True

    def set_channel_visibility(self, visible: bool, ch_idx: int | None = None) -> None:
        """Set the visibility of an existing Image node."""
        if ch_idx is None:
            ch_idx = getattr(self.sender(), "idx", 0)
        self._map_func(lambda i: setattr(i, "visible", visible), ch_idx)

    def set_channel_clims(self, clims: tuple, ch_idx: int | None = None) -> None:
        """Set the contrast limits for an existing Image node."""
        if ch_idx is None:
            ch_idx = getattr(self.sender(), "idx", 0)
        self._map_func(lambda i: setattr(i, "clim", clims), ch_idx)

    def set_channel_cmap(self, cmap: cmap.Colormap, ch_idx: int | None = None) -> None:
        """Set the colormap for an existing Image node."""
        if ch_idx is None:
            ch_idx = getattr(self.sender(), "idx", 0)
        self._map_func(lambda i: setattr(i, "cmap", cmap.to_vispy()), ch_idx)

    def _map_func(
        self, functor: Callable[[scene.visuals.Image], Any], ch_idx: int
    ) -> None:
        """Apply a function to all images that match the given axis key."""
        for axis_keys, img in self._images.items():
            if (CHANNEL, ch_idx) in axis_keys:
                functor(img)
        self._canvas.update()

    def set_range(
        self,
        x: tuple[float, float] | None = None,
        y: tuple[float, float] | None = None,
        margin: float | None = 0.05,
    ) -> None:
        """Update the range of the PanZoomCamera.

        When called with no arguments, the range is set to the full extent of the data.
        """
        self._camera.set_range(x=x, y=y, margin=margin)

    def _image_key(self, index: Mapping[str, int]) -> ImageKey:
        # gather all axes that require a unique image
        # and return as, e.g. [('c', 0), ('g', 1)]
        keys: list[tuple[str, int]] = []
        if self._channel_mode == "composite":
            keys.append((CHANNEL, index.get(CHANNEL, 0)))
        return tuple(keys)

    def set_current_index(self, index: Mapping[str, int]) -> None:
        """Set the current image index."""
        indices: list[Mapping[str, int]] = []
        if self._channel_mode != "composite":
            indices = [index]
        else:
            # if we're in composite mode, we need to update the image for each channel
            this_channel = index.get(CHANNEL)
            this_channel_exists = False
            for key in self._images:
                for axis, axis_i in key:
                    if axis == CHANNEL:
                        indices.append({**index, axis: axis_i})
                        if axis_i == this_channel:
                            this_channel_exists = True
            if not this_channel_exists:
                indices.insert(0, index)

        for index in indices:
            # otherwise, we only have a single image to update
            try:
                data = self._datastore.isel(index)
            except Exception as e:
                logging.error(f"Error getting frame for index {index}: {e}")
                continue

            if (key := self._image_key(index)) not in self._images:
                self.add_image(key, data)
            else:
                # FIXME
                # this is a hack to avoid data that hasn't arrived yet
                if data.max() != 0:
                   self._images[key].set_data(data)
        self._canvas.update()

c = itertools.count()
class StackViewer(QWidget):
    """A viewer for MDA acquisitions started by MDASequence in pymmcore-plus events."""

    def __init__(self, *, parent: QWidget | None = None):
        super().__init__(parent=parent)

        channel_mode: Literal["composite", "grayscale"] = "composite"

        self._core = CMMCorePlus.instance()
        self.datastore = DataStore()
        self._canvas = VispyViewerCanvas(self.datastore, channel_mode=channel_mode)
        self._info_bar = QLabel("Info")
        self._dims_sliders = DimsSliders()

        if channel_mode == "composite":
            self._dims_sliders.set_dimension_visible(CHANNEL, False)

        self._canvas.infoText.connect(lambda x: self._info_bar.setText(x))
        self._core.mda.events.frameReady.connect(self.on_frame_ready)
        # self.datastore.frame_ready.connect(self.on_frame_ready)
        self._dims_sliders.indexChanged.connect(self._on_dims_sliders)

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._dims_sliders)

        for i, ch in enumerate(["DAPI", "FITC"]):
            c = ChannelVisControl(i, ch)
            layout.addWidget(c)
            c.climsChanged.connect(self._canvas.set_channel_clims)
            c.cmapChanged.connect(self._canvas.set_channel_cmap)
            c.visibilityChanged.connect(self._canvas.set_channel_visibility)

    def _on_dims_sliders(self, index: dict) -> None:
        self._canvas.set_current_index(index)

    @superqt.ensure_main_thread
    def on_frame_ready(self, frame: np.narray, event: useq.MDAEvent) -> None:
        self._dims_sliders.update_dimensions(event.index)
