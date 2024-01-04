from __future__ import annotations

import sys

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets
from useq import MDASequence

from pymmcore_widgets._mda._stack_viewer import StackViewer

size = 1028

mmcore = CMMCorePlus.instance()
mmcore.loadSystemConfiguration()

mmcore.setProperty("Camera", "OnCameraCCDXSize", size)
mmcore.setProperty("Camera", "OnCameraCCDYSize", size)
mmcore.setProperty("Camera", "StripeWidth", 0.7)
qapp = QtWidgets.QApplication(sys.argv)

sequence = MDASequence(
    channels=({"config": "FITC", "exposure": 10}, {"config": "DAPI", "exposure": 1}),
    time_plan={"interval": 0.2, "loops": 100},
    axis_order="tpcz",
)


w = StackViewer(sequence=sequence, mmcore=mmcore)
w.show()

mmcore.run_mda(sequence)
qapp.exec_()
