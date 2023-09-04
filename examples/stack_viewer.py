import sys

from pymmcore_plus import CMMCorePlus
from useq import MDASequence
from qtpy import QtWidgets

from pymmcore_widgets._mda._stack_viewer import StackViewer
from pymmcore_widgets._mda._datastore import QLocalDataStore


size = 1028

mmcore = CMMCorePlus.instance()
mmcore.loadSystemConfiguration()

mmcore.setProperty("Camera", "OnCameraCCDXSize", size)
mmcore.setProperty("Camera", "OnCameraCCDYSize", size)
mmcore.setProperty("Camera", "StripeWidth", 0.7)
qapp = QtWidgets.QApplication(sys.argv)

sequence = MDASequence(
    channels=({"config": "FITC", "exposure": 1}, {"config": "DAPI", "exposure": 1}),
    time_plan={"interval": 0.5, "loops": 20},
    axis_order="tpcz",
)

datastore = QLocalDataStore((40, 1, 2, size, size), mmcore=mmcore)
w = StackViewer(sequence=sequence, mmcore=mmcore, datastore=datastore)
w.show()

mmcore.run_mda(sequence)
qapp.exec_()