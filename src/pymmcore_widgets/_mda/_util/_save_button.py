from pathlib import Path

import numpy as np
from fonticon_mdi6 import MDI6
from pymmcore_plus import OMETiffWriter
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QFileDialog, QPushButton, QWidget
from superqt import fonticon
from useq import MDAEvent, MDASequence

from .._datastore import QLocalDataStore


class SaveButton(QPushButton):
    def __init__(
        self,
        datastore: QLocalDataStore,
        seq: MDASequence | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        # self.setFont(QFont('Arial', 50))
        self.setMinimumHeight(40)
        self.setIcon(fonticon.icon(MDI6.content_save_outline, color="gray"))
        self.setIconSize(QSize(30, 30))
        self.setFixedSize(40, 40)
        self.clicked.connect(self.on_click)
        self.save_loc = Path.home()
        self.datastore = datastore
        self.seq = seq

    def on_click(self):
        self.save_loc, _ = QFileDialog.getSaveFileName(directory=self.save_loc)
        saver = OMETiffWriter(self.save_loc)
        shape = self.datastore.array.shape
        indices = np.stack(
            np.meshgrid(
                range(shape[0]), range(shape[1]), range(shape[2]), range(shape[3])
            ),
            -1,
        ).reshape(-1, 4)
        for index in indices:
            event_index = {"t": index[0], "z": index[1], "c": index[2], "g": index[3]}
            # TODO: we should also save the event info in the datastore and the metadata.
            saver.frameReady(
                self.datastore.array[*index],
                MDAEvent(index=event_index, sequence=self.seq),
                {},
            )
