from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Mapping

import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QTimer, Signal
from superqt.cmap._cmap_utils import try_cast_colormap

from pymmcore_widgets._mda._util._channel_row import ChannelRow
from pymmcore_widgets._mda._util._labeled_slider import LabeledVisibilitySlider

DIMENSIONS = ["t", "z", "c", "p", "g"]
AUTOCLIM_RATE = 1  # Hz   0 = inf

try:
    from vispy import scene
except ImportError as e:
    raise ImportError(
        "vispy is required for StackViewer. "
        "Please run `pip install pymmcore-widgets[image]`"
    ) from e

if TYPE_CHECKING:
    import cmap
    from qtpy.QtWidgets import QWidget
    from useq import MDAEvent, MDASequence
    from vispy.scene.events import SceneMouseEvent

    from pymmcore_widgets._mda._datastore import QLocalDataStore


class StackViewer(QtWidgets.QWidget):
    """A viewer for MDA acquisitions started by MDASequence in pymmcore-plus events."""

    _slider_settings = Signal(dict)
    _new_channel = Signal(int, str)

    def __init__(
        self,
        datastore: QLocalDataStore,
        sequence: MDASequence | None = None,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self.sequence = sequence

        self._clim = "auto"
        self.cmap_names = ["Greys", "cyan", "magenta"]
        self.cmaps = [try_cast_colormap(x) for x in self.cmap_names]
        self.display_index = {dim: 0 for dim in DIMENSIONS}

        self.setLayout(QtWidgets.QVBoxLayout())
        self.construct_canvas()
        self.layout().addWidget(self._canvas.native)

        self.info_bar = QtWidgets.QLabel()
        self.info_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.layout().addWidget(self.info_bar)

        self._create_sliders(sequence)

        self.datastore = datastore
        self._mmc.mda.events.sequenceStarted.connect(self.on_sequence_start)
        self.datastore.frame_ready.connect(self.on_frame_ready)

        self._new_channel.connect(self.channel_row.box_visibility)

        self.images: list[scene.visuals.Image] = []
        self.frame = 0
        self.ready = False
        self.current_channel = 0

        self.clim_timer = QtCore.QTimer()
        self.clim_timer.setInterval(int(1000 // AUTOCLIM_RATE))
        self.clim_timer.timeout.connect(self.on_clim_timer)

        if sequence:
            self.on_sequence_start(sequence)

    def construct_canvas(self) -> None:
        img_size = (self._mmc.getImageHeight(), self._mmc.getImageWidth())
        if img_size == (0, 0):
            img_size = (512, 512)
        self._canvas = scene.SceneCanvas(
            size=img_size, parent=self, autoswap=False, vsync=True, keys=None
        )
        self._canvas._send_hover_events = True
        self._canvas.events.mouse_move.connect(self.on_mouse_move)
        self.view = self._canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)
        self.view.camera.flip = (0, 1, 0)
        self.view.camera.set_range()

    def on_sequence_start(self, sequence: MDASequence) -> None:
        """Sequence started by the mmcore. Adjust our settings, make layers etc."""
        self.ready = False
        self.sequence = sequence

        # Sliders
        for dim in DIMENSIONS[:3]:
            if sequence.sizes.get(dim, 1) > 1:
                self._slider_settings.emit(
                    {"index": dim, "show": True, "max": sequence.sizes[dim] - 1}
                )
            else:
                self._slider_settings.emit({"index": dim, "show": False, "max": 1})

        # Channels
        nc = sequence.sizes["c"]
        self.images = []
        for i in range(nc):
            image = scene.visuals.Image(
                np.zeros(self._canvas.size).astype(self.datastore.dtype),
                parent=self.view.scene,
                cmap=self.cmaps[i].to_vispy(),
                clim=(0, 1),
            )
            if i > 0:
                image.set_gl_state("additive", depth_test=False)
            self.images.append(image)
            self.current_channel = i
            self._new_channel.emit(i, sequence.channels[i].config)
        self.ready = True

    def _handle_channel_clim(
        self, values: tuple[int, int], channel: int, set_autoscale: bool = True
    ) -> None:
        self.images[channel].clim = values
        if self.channel_row.boxes[channel].autoscale_chbx.isChecked() and set_autoscale:
            self.channel_row.boxes[channel].autoscale_chbx.setCheckState(
                QtCore.Qt.Unchecked
            )
        self._canvas.update()

    def _handle_channel_cmap(self, colormap: cmap.Colormap, channel: int) -> None:
        self.images[channel].cmap = colormap.to_vispy()
        self._canvas.update()

    def _handle_channel_visibility(self, state: bool, channel: int) -> None:
        self.images[channel].visible = self.channel_row.boxes[
            channel
        ].show_channel.isChecked()
        self._canvas.update()

    def _handle_channel_autoscale(self, state: bool, channel: int) -> None:
        slider = self.channel_row.boxes[channel].slider
        if state == 0:
            self._handle_channel_clim(slider.value(), channel, set_autoscale=False)
        else:
            clim = (
                slider.minimum(),
                slider.maximum(),
            )
            self._handle_channel_clim(clim, channel, set_autoscale=False)

    def _handle_channel_choice(self, channel: int) -> None:
        self.current_channel = channel

    def _create_sliders(self, sequence: MDASequence | None = None) -> None:
        n_channels = 5 if sequence is None else sequence.sizes["c"]
        self.channel_row = ChannelRow(n_channels, self.cmaps)
        self.channel_row.visible.connect(self._handle_channel_visibility)
        self.channel_row.autoscale.connect(self._handle_channel_autoscale)
        self.channel_row.new_clims.connect(self._handle_channel_clim)
        self.channel_row.new_cmap.connect(self._handle_channel_cmap)
        self.channel_row.selected.connect(self._handle_channel_choice)
        self.layout().addWidget(self.channel_row)

        if sequence is not None:
            dims = [x for x in sequence.sizes.keys() if sequence.sizes[x] > 0]
        else:
            dims = DIMENSIONS
        if "c" in dims:
            dims.remove("c")
        self.sliders: list[LabeledVisibilitySlider] = []
        for dim in dims:
            slider = LabeledVisibilitySlider(dim, orientation=QtCore.Qt.Horizontal)
            slider.valueChanged.connect(self.on_display_timer)
            self._slider_settings.connect(slider._visibility)
            self.layout().addWidget(slider)
            slider.hide()
            self.sliders.append(slider)
        # print("Number of sliders constructed: ", len(self.sliders))

    def on_mouse_move(self, event: SceneMouseEvent) -> None:
        """Mouse moved on the canvas, display the pixel value and position."""
        transform = self.images[self.current_channel].get_transform("canvas", "visual")
        p = [int(x) for x in transform.map(event.pos)]
        if p[0] < 0 or p[1] < 0:
            info = f"[{p[0]}, {p[1]}]"
            self.info_bar.setText(info)
            return
        try:
            pos = f"[{p[0]}, {p[1]}]"
            value = f"{self.images[self.current_channel]._data[p[1], p[0]]}"
            info = f"{pos}: {value}"
            self.info_bar.setText(info)
        except IndexError:
            info = f"[{p[0]}, {p[1]}]"
            self.info_bar.setText(info)

    def on_display_timer(self) -> None:
        """Update display, usually triggered by QTimer started by slider click."""
        old_index = self.display_index.copy()
        for slider in self.sliders:
            self.display_index[slider.name] = slider.value()
        if old_index == self.display_index:
            return
        if (sequence := self.sequence) is None:
            return
        for c in range(sequence.sizes.get("c", 0)):
            frame = self.datastore.get_frame(
                (self.display_index["t"], self.display_index["z"], c)
            )
            self.display_image(frame, c)
        self._canvas.update()

    def on_frame_ready(self, event: MDAEvent) -> None:
        """Frame received from acquisition, display the image, update sliders etc."""
        if not self.ready:
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.on_frame_ready(event))
            timer.start(100)
            return
        indices = self.complement_indices(event.index)
        img = self.datastore.get_frame((indices["t"], indices["z"], indices["c"]))

        # Update internal image parameters
        if sum(indices.values()) == 0:
            self.view.camera.rect = (0, 0, img.shape[0], img.shape[1])
        # Update display
        self.display_image(img, indices["c"])
        self._set_sliders(indices)
        # Handle Autoscaling
        slider = self.channel_row.boxes[indices["c"]].slider
        slider.setRange(
            min(slider.minimum(), img.min()), max(slider.maximum(), img.max())
        )
        if self.channel_row.boxes[indices["c"]].autoscale_chbx.isChecked():
            slider.setValue(
                [min(slider.minimum(), img.min()), max(slider.maximum(), img.max())]
            )
        self.on_clim_timer(indices["c"])

    def _set_sliders(self, indices: dict) -> None:
        """New indices from outside the sliders, update."""
        for slider in self.sliders:
            slider.blockSignals(True)
            slider.setValue(indices[slider.name])
            slider.blockSignals(False)

    def display_image(self, img: np.ndarray, channel: int = 0) -> None:
        self.images[channel].set_data(img)

    def on_clim_timer(self, channel: int | None = None) -> None:
        channel_list = (
            list(range(len(self.channel_row.boxes))) if channel is None else [channel]
        )
        for channel in channel_list:
            if (
                self.channel_row.boxes[channel].autoscale_chbx.isChecked()
                and self.images[channel].visible
            ):
                # TODO: percentile here, could be in gui
                clim = np.percentile(self.images[channel]._data, [0, 100])
                self.images[channel].clim = clim

    def complement_indices(self, index: Mapping[str, int]) -> dict:
        """MDAEvents not always have all the dimensions, complement."""
        indices = dict(copy.deepcopy(dict(index)))
        for i in DIMENSIONS:
            if i not in indices:
                indices[i] = 0
        return indices
