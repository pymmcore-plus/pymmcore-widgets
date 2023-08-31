import copy

import numpy as np
import numpy.typing as npt
from pymmcore_plus import CMMCorePlus
from qtpy import QtCore, QtWidgets
from useq import MDAEvent

DIMENSIONS = ["t", "c", "z"]


class QLocalDataStore(QtCore.QObject):
    """DataStore that connects directly to the mmcore frameReady event and saves the data for
    a consumer like Canvas to show it.
    """

    frame_ready = QtCore.Signal(MDAEvent)

    def __init__(
        self,
        shape: tuple,
        dtype: npt.DTypeLike = np.uint16,
        parent: QtWidgets.QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)
        self.dtype = np.dtype(dtype)
        self.array = np.ndarray(shape, dtype=self.dtype)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.listener = self.EventListener(mmcore)
        self.listener.start()
        self.listener.frame_ready.connect(self.new_frame)

    class EventListener(QtCore.QThread):
        "Receive events in a separate thread."

        frame_ready = QtCore.Signal(np.ndarray, MDAEvent)

        def __init__(self, mmcore: CMMCorePlus):
            super().__init__()
            self._mmc = mmcore
            self._mmc.mda.events.frameReady.connect(self.on_frame_ready)

        def on_frame_ready(self, img: np.ndarray, event: MDAEvent):
            self.frame_ready.emit(img, event)

        def closeEvent(self, event):
            super().exit()
            event.accept()

    def new_frame(self, img: np.ndarray, event: MDAEvent):
        self.shape = img.shape
        indices = self.complement_indices(event)
        try:
            self.array[indices["t"], indices["z"], indices["c"], :, :] = img
        except IndexError:
            self.correct_shape(self, indices)
            self.new_frame(img, event)
            return
        self.frame_ready.emit(event)

    def get_frame(self, key):
        return self.array[*key, :, :]

    def complement_indices(self, event):
        indices = dict(copy.deepcopy(dict(event.index)))
        for i in DIMENSIONS:
            if i not in indices:
                indices[i] = 0
        return indices

    def correct_shape(self, indices: tuple) -> None:
        "The initialised shape does not fit the data, extend the array."
        min_shape = [indices["t"], indices["z"], indices["c"]]
        diff = [x - y + 1 for x, y in zip(min_shape, self.array.shape[:-2])]
        for i, app in enumerate(diff):
            if app > 0:
                if i == 0:  # handle time differently, double the size
                    app = self.array.shape[0]
                append_shape = [*self.array.shape[:i], app, *self.array.shape[i + 1 :]]
                self.array = np.append(
                    self.array, np.zeros(append_shape, self.array.dtype), axis=i
                )

    def __del__(self):
        self.listener.exit()
        self.listener.wait()
