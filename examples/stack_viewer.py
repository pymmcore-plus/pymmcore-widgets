from __future__ import annotations

import sys

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets
from useq import MDASequence

from pymmcore_widgets.experimental import StackViewer

size = 2048

mmcore = CMMCorePlus.instance()
mmcore.loadSystemConfiguration()

mmcore.setProperty("Camera", "OnCameraCCDXSize", size)
mmcore.setProperty("Camera", "OnCameraCCDYSize", size)
mmcore.setProperty("Camera", "StripeWidth", 0.7)
qapp = QtWidgets.QApplication(sys.argv)

sequence = MDASequence(
    channels=(
        {"config": "DAPI", "exposure": 10},
        {"config": "FITC", "exposure": 1},
        {"config": "Cy3", "exposure": 1},
    ),
    time_plan={"interval": 0.2, "loops": 2},
    # grid_plan={"rows": 2, "columns": 2},
)

w = StackViewer(sequence=sequence, mmcore=mmcore, transform=(90, True, False))
w.show()

mmcore.run_mda(sequence)
qapp.exec()
