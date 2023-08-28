import numpy as np
import copy

from qtpy import QtWidgets, QtCore, QtGui

from pymmcore_plus import CMMCorePlus
from useq import MDASequence, Channel

from pymmcore_widgets._mda._util._qt import ChannelBox, LabeledVisibilitySlider
from pymmcore_widgets._mda._datastore import QLocalDataStore

DIMENSIONS = ["t", "z", "c", "p", "g"]
AUTOCLIM_RATE = 1 #Hz   0 = inf

try:
    from vispy import scene, color
except ImportError as e:
    raise ImportError(
        "vispy is required for ImagePreview. "
        "Please run `pip install pymmcore-widgets[image]`"
    ) from e


class StackViewer(QtWidgets.QWidget):
    """A canvas to follow MDA acquisitions started by MDASequence events. Works for remote and local
    datastores. QEventCosumer handles the connection to the correct events for each version."""
    _slider_settings = QtCore.Signal(dict)
    _new_channel = QtCore.Signal(int, str)

    def __init__(self,
                 mmcore: CMMCorePlus = None,
                 datastore: QLocalDataStore = None,
                 parent: QtWidgets.QWidget|None = None):

        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._clim = 'auto'
        self.cmaps = [color.Colormap([[0, 0, 0], [1, 1, 0]]),
                      color.Colormap([[0, 0, 0], [1, 0, 1]]),
                      color.Colormap([[0, 0, 0], [0, 1, 1]]),
                      color.Colormap([[0, 0, 0], [1, 0, 0]]),
                      color.Colormap([[0, 0, 0], [0, 1, 0]]),
                      color.Colormap([[0, 0, 0], [0, 0, 1]])]

        self.display_index = {dim: 0 for dim in DIMENSIONS}

        self.setLayout(QtWidgets.QVBoxLayout())
        self.construct_canvas()
        self.layout().addWidget(self._canvas.native)

        self.info_bar = QtWidgets.QLabel()
        self.info_bar.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.layout().addWidget(self.info_bar)

        self._create_sliders()

        self._mmc = mmcore or CMMCorePlus.instance()
        self.datastore = datastore
        self._mmc.mda.events.sequenceStarted.connect(self.on_sequence_start)
        self.datastore.frame_ready.connect(self.on_frame_ready)

        self._new_channel.connect(self._handle_chbox_visibility)
        self.images = []

        self.frame = 0

        self.clim_timer = QtCore.QTimer()
        self.clim_timer.setInterval(int(1000 // AUTOCLIM_RATE))
        self.clim_timer.timeout.connect(self.on_clim_timer)

    def construct_canvas(self):
        self._clims = "auto"
        self._canvas = scene.SceneCanvas( size=(512, 512), parent=self,
                                         autoswap=False, vsync=True, keys=None)
        self._canvas._send_hover_events = True
        self._canvas.events.mouse_move.connect(self.on_mouse_move)
        self.view = self._canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)
        self.view.camera.flip = (0, 1, 0)
        self.view.camera.set_range()

    def on_sequence_start(self, sequence: MDASequence):
        self.sequence = sequence
        self.handle_sliders(sequence)
        self.handle_channels(sequence, self.datastore)

    def handle_channels(self, sequence: MDASequence, array: np.ndarray):
        nc = sequence.sizes['c']
        self.images = []
        for i in range(nc):
            image = scene.visuals.Image(np.zeros(self._canvas.size).astype(array.dtype),
                                        parent=self.view.scene, cmap=self.cmaps[i], clim=[0,1])
            if i > 0:
                image.set_gl_state('additive', depth_test=False)
            self.images.append(image)
            self.current_channel = i
            self._new_channel.emit(i, sequence.channels[i].config)

    def _handle_chbox_visibility(self, i: int, name: str):
        self.channel_boxes[i].show()
        self.channel_boxes[i].autoscale.setChecked(True)
        self.channel_boxes[i].show_channel.setText(name)
        self.channel_boxes[i].channel = name
        self.channel_boxes[i].mousePressEvent(None)

    def _handle_channel_choice(self, channel: str):
        for idx, channel_box in enumerate(self.channel_boxes):
            if channel_box.channel != channel:
                channel_box.setStyleSheet("ChannelBox{border: 1px solid}")
            else:
                self.current_channel = idx

    def _handle_channel_clim(self, values, channel: int, set_autoscale=True):
        self.images[channel].clim = values
        if self.channel_boxes[channel].autoscale.isChecked() and set_autoscale:
            self.channel_boxes[channel].autoscale.setCheckState(QtCore.Qt.Unchecked)
        self._canvas.update()

    def _handle_channel_cmap(self, my_color, channel: int):
        my_color = [x//255 for x in my_color.getRgb()[:3]]
        self.images[channel].cmap = color.Colormap([[0, 0, 0], my_color])
        self._canvas.update()

    def _handle_channel_visibility(self, state, channel: int):
        self.images[channel].visible = self.channel_boxes[channel].show_channel.isChecked()
        self._canvas.update()

    def _handle_channel_autoscale(self, state, channel: int):
        if state == 0:
            slider = self.channel_boxes[channel].slider
            self._handle_channel_clim(slider.value(), channel, set_autoscale=False)
        else:
            clim = (np.min(self.images[channel]._data), np.max(self.images[channel]._data))
            self._handle_channel_clim(clim, channel, set_autoscale=False)

    def handle_sliders(self, sequence: MDASequence):
        for dim in DIMENSIONS[:3]:
            if sequence.sizes[dim] > 1:
                self._slider_settings.emit({"index": dim,"show": True,
                                            "max": sequence.sizes[dim] - 1})
            else:
                self._slider_settings.emit({"index": dim, "show": False, "max": 1})

    def _create_sliders(self,):
        dims = DIMENSIONS
        dims.remove('c')
        self.channel_row = QtWidgets.QWidget()
        self.channel_row.setLayout(QtWidgets.QHBoxLayout())
        self.channel_row.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Fixed)
        self.layout().addWidget(self.channel_row)

        self.sliders = []
        for dim in dims:
            slider = LabeledVisibilitySlider(dim,  orientation=QtCore.Qt.Horizontal)
            slider.valueChanged[int, str].connect(self.on_display_timer)

            self._slider_settings.connect(slider._visibility)
            self.layout().addWidget(slider)
            slider.hide()
            self.sliders.append(slider)

        self.channel_boxes = []
        for i in range(5):
            channel_box = ChannelBox(Channel(config="empty"), CMAPS=self.cmaps)
            channel_box.show_channel.stateChanged.connect(lambda state, i=i: self._handle_channel_visibility(state, i))
            channel_box.autoscale.stateChanged.connect(lambda state, i=i: self._handle_channel_autoscale(state, i))
            channel_box.slider.sliderMoved.connect(lambda values, i=i: self._handle_channel_clim(values, i))
            channel_box.color_choice.selectedColor.connect(lambda color, i=i: self._handle_channel_cmap(color, i))
            channel_box.color_choice.setColor(i)
            channel_box.clicked.connect(self._handle_channel_choice)
            channel_box.mousePressEvent(None)
            channel_box.hide()
            self.current_channel = i
            self.channel_boxes.append(channel_box)
            self.channel_row.layout().addWidget(channel_box)

    def on_mouse_move(self, event):
        transform = self.images[self.current_channel].get_transform('canvas', 'visual')
        p = [int(x) for x in transform.map(event.pos)]
        if p[0] < 0 or p[1] < 0:
            info = f"[{p[0]}, {p[1]}]"
            self.info_bar.setText(info)
            return
        try:
            info = f"[{p[0]}, {p[1]}] = {self.images[self.current_channel]._data[p[1], p[0]]}"
            self.info_bar.setText(info)
        except IndexError:
            info = f"[{p[0]}, {p[1]}]"
            self.info_bar.setText(info)

    def on_display_timer(self, _=None):
        old_index = self.display_index.copy()
        for slider in self.sliders:
            self.display_index[slider.name] = slider.value()
        if old_index == self.display_index:
            return
        for c in range(self.sequence.sizes['c']):
            frame = self.datastore.get_frame([self.display_index['t'], self.display_index['z'],  c])
            self.display_image(frame, c)
        self._canvas.update()

    def on_frame_ready(self, event):
        indices = self.complement_indices(event.index)
        img = self.datastore.get_frame([indices["t"], indices["z"], indices["c"]])
        shape = img.shape
        self.width, self.height = shape
        if sum(indices.values()) == 0:
            self.view.camera.rect = ((0, 0, *shape))
        self.display_image(img, indices["c"])
        self._set_sliders(indices)
        slider = self.channel_boxes[indices["c"]].slider
        slider.setRange(min(slider.minimum(), img.min()), max(slider.maximum(), img.max()))
        if self.channel_boxes[indices["c"]].autoscale.isChecked():
            slider.setValue([min(slider.minimum(), img.min()), max(slider.maximum(), img.max())])
        self.on_clim_timer(indices["c"])

    def _set_sliders(self, indices: dict):
        for slider in self.sliders:
            slider.blockSignals(True)
            slider.setValue(indices[slider.name])
            slider.blockSignals(False)

    def display_image(self, img: np.ndarray, channel=0):
        self.images[channel].set_data(img)

    def on_clim_timer(self, channel=None):
        channel_list = list(range(len(self.channel_boxes))) if channel is None else [channel]
        for channel in channel_list:
            if self.channel_boxes[channel].autoscale.isChecked() and self.images[channel].visible:
                clim = np.percentile(self.images[channel]._data, [0, 100])
                self.images[channel].clim = clim

    def complement_indices(self, index):
        indeces = dict(copy.deepcopy(dict(index)))
        for i in DIMENSIONS:
            if i not in indeces:
                indeces[i] = 0
        return indeces


if __name__ == "__main__":
    size = 1028
    from pymmcore_widgets._mda._datastore import QLocalDataStore
    import sys
    mmcore = CMMCorePlus.instance()
    mmcore.loadSystemConfiguration()

    mmcore.setProperty("Camera", "OnCameraCCDXSize", size)
    mmcore.setProperty("Camera", "OnCameraCCDYSize", size)
    mmcore.setProperty("Camera", "StripeWidth", 0.7)
    qapp = QtWidgets.QApplication(sys.argv)

    datastore = QLocalDataStore([40, 1, 2, size, size], mmcore=mmcore)
    w = StackViewer(mmcore=mmcore, datastore=datastore)
    w.show()

    sequence = MDASequence(
    channels=[{"config": "FITC", "exposure": 1}, {"config": "DAPI", "exposure": 1}],
    time_plan={"interval": 0.5, "loops": 20},
    axis_order="tpcz", )

    mmcore.run_mda(sequence)
    qapp.exec_()
