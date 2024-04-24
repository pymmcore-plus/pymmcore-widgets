from __future__ import annotations

from contextlib import suppress
from itertools import cycle
from typing import TYPE_CHECKING, Any, Hashable, Literal, Mapping
from warnings import warn

import cmap
import superqt
import useq
from psygnal import Signal
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import OMEZarrWriter
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from superqt import QLabeledSlider
from superqt.iconify import QIconifyIcon
from vispy import scene

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtCore import QTimerEvent
    from vispy.scene.events import SceneMouseEvent


CHANNEL = "c"
COLORMAPS = cycle(
    [cmap.Colormap("green"), cmap.Colormap("magenta"), cmap.Colormap("cyan")]
)


def try_cast_colormap(val: Any) -> cmap.Colormap | None:
    """Try to cast `val` to a cmap.Colormap instance, return None if it fails."""
    if isinstance(val, cmap.Colormap):
        return val
    with suppress(Exception):
        return cmap.Colormap(val)
    return None


# FIXME: get rid of this thin subclass
class DataStore(OMEZarrWriter):
    frame_ready = Signal(useq.MDAEvent)

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
        self._images: dict[Hashable, scene.visuals.Image] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas.native)

        self.set_range()

    def _on_mouse_move(self, event: SceneMouseEvent) -> None:
        """Mouse moved on the canvas, display the pixel value and position."""
        images = []
        # Get the images the mouse is over
        while image := self._canvas.visual_at(event.pos):
            if image in self._images.values():
                images.append(image)
            image.interactive = False
        for img in self._images.values():
            img.interactive = True
        if not images:
            return

        tform = images[0].get_transform("canvas", "visual")
        px, py, *_ = (int(x) for x in tform.map(event.pos))
        text = f"[{py}, {px}]"
        for c, img in enumerate(images):
            value = f"{img._data[py, px]}"
            text += f" c{c}: {value}"
        self.infoText.emit(text)

    def add_image(self, key: Hashable, data: np.ndarray | None = None) -> None:
        """Add a new Image node to the scene."""
        if self._channel_mode == "composite":
            cmap = next(COLORMAPS).to_vispy()
        else:
            cmap = "grays"
        self._images[key] = img = scene.visuals.Image(
            data, cmap=cmap, parent=self._view.scene
        )
        img.set_gl_state("additive", depth_test=False)
        img.interactive = True
        self.set_range()

    def remove_image(self, key: Hashable) -> None:
        """Remove an Image node from the scene."""
        try:
            image = self._images.pop(key)
        except KeyError:
            warn(f"Image {key} not found in ViewerCanvas", stacklevel=2)
            return
        image.parent = None

    def set_image_data(self, key: Hashable, data: np.ndarray) -> None:
        """Set the data for an existing Image node."""
        self._images[key].set_data(data)
        self._canvas.update()

    def set_image_cmap(self, key: Hashable, cmap: str) -> None:
        """Set the colormap for an existing Image node."""
        self._images[key].cmap = cmap
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

    def _image_key(self, index: dict) -> Hashable:
        dims_needing_images = set()
        if self._channel_mode == "composite":
            dims_needing_images.add(CHANNEL)

        return tuple((dim, index.get(dim)) for dim in dims_needing_images)

    def set_current_index(self, index: Mapping[str, int]) -> None:
        """Set the current image index."""
        cidx = ((CHANNEL, index.get("c")),)
        if self._channel_mode == "composite" and cidx in self._images:
            # if we're in composite mode, we need to update the image for each channel
            for key, _ in self._images.items():
                # FIXME
                try:
                    image_data = self._datastore.isel(index, c=key[0][1])
                except IndexError:
                    print("ERR", key, index)
                    continue
                self.set_image_data(key, image_data)

        else:
            # otherwise, we only have a single image to update
            frame = self._datastore.isel(index)
            if (key := self._image_key(index)) not in self._images:
                self.add_image(key, frame)
            else:
                self.set_image_data(key, frame)


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
        self.datastore.frame_ready.connect(self.on_frame_ready)
        self._dims_sliders.indexChanged.connect(self._on_dims_sliders)

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._dims_sliders)

    def _on_dims_sliders(self, index: dict) -> None:
        self._canvas.set_current_index(index)

    @superqt.ensure_main_thread
    def on_frame_ready(self, event: useq.MDAEvent) -> None:
        self._dims_sliders.update_dimensions(event.index)
