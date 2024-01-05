from pathlib import Path

import zarr
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import QFileDialog, QPushButton, QWidget
from superqt import fonticon
from useq import MDASequence

from pymmcore_widgets._mda._datastore import QOMEZarrDatastore


class SaveButton(QPushButton):
    def __init__(
        self,
        datastore: QOMEZarrDatastore,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        # self.setFont(QFont('Arial', 50))
        self.setMinimumHeight(40)
        self.setIcon(fonticon.icon(MDI6.content_save_outline, color="gray"))
        self.setIconSize(QSize(30, 30))
        self.setFixedSize(40, 40)
        self.clicked.connect(self._on_click)

        self.datastore = datastore
        self.save_loc = Path.home()

    def _on_click(self) -> None:
        self.save_loc, _ = QFileDialog.getSaveFileName(directory=str(self.save_loc))
        if self.save_loc:
            dir_store = zarr.DirectoryStore(self.save_loc)
            zarr.copy_store(self.datastore._group.attrs.store, dir_store)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        return super().closeEvent(a0)


if __name__ == "__main__":
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QApplication
    from useq import MDASequence

    from pymmcore_widgets._mda._datastore import QOMEZarrDatastore

    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()

    app = QApplication([])
    seq = MDASequence(
        time_plan={"interval": 0.01, "loops": 10},
        z_plan={"range": 5, "step": 1},
        channels=[{"config": "DAPI", "exposure": 1}, {"config": "FITC", "exposure": 1}],
    )
    datastore = QOMEZarrDatastore()
    mmc.mda.events.sequenceStarted.connect(datastore.sequenceStarted)
    mmc.mda.events.frameReady.connect(datastore.frameReady)

    widget = SaveButton(datastore, mmc)
    mmc.run_mda(seq)
    widget.show()
    app.exec_()
