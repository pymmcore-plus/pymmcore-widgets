import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget
from pymmcore_widgets._stage_recorder import StageRecorder

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

mmc.setProperty("Camera", "Mode", "Noise")

rec = StageRecorder()
rec.poll_xy_stage = True
rec.show()

s = StageWidget(mmc.getXYStageDevice())
s.setStep(300)
s.show()


seq = useq.MDASequence(
    channels=["FITC"],
    grid_plan=useq.GridRowsColumns(
        rows=4,
        columns=4,
        fov_width=mmc.getImageWidth() * mmc.getPixelSizeUm(),
        fov_height=mmc.getImageHeight() * mmc.getPixelSizeUm(),
    ),
    stage_positions=[(0, 0)],
)

mmc.run_mda(seq)

app.exec()
