from __future__ import annotations

from pymmcore_plus import CMMCorePlus, configure_logging
from qtpy import QtWidgets
from useq import MDASequence

from pymmcore_widgets._stack_viewer2._stack_viewer import MDAViewer

configure_logging(stderr_level="WARNING")

mmcore = CMMCorePlus.instance()
mmcore.loadSystemConfiguration()
mmcore.defineConfig("Channel", "DAPI", "Camera", "Mode", "Artificial Waves")
mmcore.defineConfig("Channel", "FITC", "Camera", "Mode", "Noise")

sequence = MDASequence(
    channels=(
        {"config": "DAPI", "exposure": 10},
        {"config": "FITC", "exposure": 80},
        # {"config": "Cy5", "exposure": 20},
    ),
    stage_positions=[(0, 0), (1, 1)],
    z_plan={"range": 2, "step": 0.4},
    time_plan={"interval": 0.8, "loops": 2},
    # grid_plan={"rows": 2, "columns": 1},
)


qapp = QtWidgets.QApplication([])
v = MDAViewer()
v.show()

mmcore.run_mda(sequence, output=v.datastore)
qapp.exec()
