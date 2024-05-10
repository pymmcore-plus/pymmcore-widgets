import sys
from queue import Queue

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets
from useq import MDAEvent

from pymmcore_widgets._stack_viewer_v2._mda_viewer import MDAViewer

app = QtWidgets.QApplication(sys.argv)
mmcore = CMMCorePlus.instance()
mmcore.loadSystemConfiguration()

canvas = MDAViewer()
canvas.show()

q = Queue()
mmcore.run_mda(iter(q.get, None), output=canvas.data)
for i in range(10):
    for c in range(2):
        q.put(MDAEvent(index={"t": i, "c": c}, exposure=1))
q.put(None)

app.exec()
