"""Example usage of the SnapButton class."""

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget
from pymmcore_widgets._stage_tracker import StageTracker

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

track = StageTracker()
track.poll_xy_stage = True
track.show()

seq = useq.MDASequence(
    channels=[{"config": "FITC", "exposure": 200}],
    grid_plan=useq.GridRowsColumns(
        rows=4,
        columns=4,
        fov_width=mmc.getImageWidth() * mmc.getPixelSizeUm(),
        fov_height=mmc.getImageHeight() * mmc.getPixelSizeUm(),
    ),
    stage_positions=[(0, 0)],
)

mmc.run_mda(seq)

s = StageWidget(mmc.getXYStageDevice())
s.setStep(300)
s.show()

app.exec()
