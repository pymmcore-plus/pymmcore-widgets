"""Example usage of the SnapButton class."""

import useq
from pymmcore_plus import CMMCorePlus

# from pymmcore_widgets import PropertyBrowser, MDAWidget, GroupPresetTableWidget
from pymmcore_widgets._stage_recorder_no_images import StageTracker
from pymmcore_widgets._stage_recorder_with_images import StageRecorder

mmc = CMMCorePlus().instance()
cfg = r"c:\Users\NIC\Desktop\mm\Ti2.cfg"
# mmc.loadSystemConfiguration(cfg)
mmc.loadSystemConfiguration()

# mmc.setProperty("Camera", "Mode", "Noise")

rec = StageRecorder()
rec.show()

track = StageTracker()
track.show()

# gp = GroupPresetTableWidget()
# gp.show()

# m = MDAWidget()
# m.show()

# pb = PropertyBrowser()
# pb.show()

# s = StageWidget(mmc.getXYStageDevice())
# s.show()


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

seq1 = useq.MDASequence(
    channels=["FITC"],
    grid_plan=useq.RandomPoints(
        num_points=10,
        max_width=-5000,
        max_height=5000,
        shape="rectangle",
        fov_width=mmc.getImageWidth() * mmc.getPixelSizeUm(),
        fov_height=mmc.getImageHeight() * mmc.getPixelSizeUm(),
        allow_overlap=False,
    ),
    stage_positions=[(0, 0)],
)
