from __future__ import annotations

import copy

import numpy as np
import numpy.typing as npt
from pymmcore_plus import CMMCorePlus
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QWidget
from qtpy.QtCore import Signal
from useq import MDAEvent

DIMENSIONS = ["t", "c", "z"]


class QLocalDataStore(QtCore.QObject):
    """Connects directly to mmcore frameReady and saves the data in a numpy array."""

    frame_ready = Signal(MDAEvent)

    def __init__(
        self,
        shape: tuple[int, ...],
        dtype: npt.DTypeLike = np.uint16,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)
        self.dtype = np.dtype(dtype)
        self.array: np.ndarray = np.ndarray(shape, dtype=self.dtype)

        self._mmc: CMMCorePlus = mmcore or CMMCorePlus.instance()

        self.listener = self.EventListener(self._mmc)
        self.listener.start()
        self.listener.frame_ready.connect(self.new_frame)

    class EventListener(QtCore.QThread):
        """Receive events in a separate thread."""

        frame_ready = Signal(np.ndarray, MDAEvent)

        def __init__(self, mmcore: CMMCorePlus):
            super().__init__()
            self._mmc = mmcore
            self._mmc.mda.events.frameReady.connect(self.on_frame_ready)

        def on_frame_ready(self, img: np.ndarray, event: MDAEvent) -> None:
            self.frame_ready.emit(img, event)

        def closeEvent(self, event: QtGui.QCloseEvent) -> None:
            super().exit()
            event.accept()

    def new_frame(self, img: np.ndarray, event: MDAEvent) -> None:
        self.shape = img.shape
        indices = self.complement_indices(event)
        try:
            self.array[indices["t"], indices["z"], indices["c"], :, :] = img
        except IndexError:
            self.correct_shape(indices)
            self.new_frame(img, event)
            return
        self.frame_ready.emit(event)

    def get_frame(self, key: tuple | list) -> np.ndarray:
        return self.array[key]

    def complement_indices(self, event: MDAEvent) -> dict:
        indices = dict(copy.deepcopy(dict(event.index)))
        for i in DIMENSIONS:
            if i not in indices:
                indices[i] = 0
        return indices

    def correct_shape(self, indices: dict) -> None:
        """The initialised shape does not fit the data, extend the array."""
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

    def __del__(self) -> None:
        self.listener.exit()
        self.listener.wait()
