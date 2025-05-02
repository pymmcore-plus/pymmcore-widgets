from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QSplitter, QVBoxLayout, QWidget

from pymmcore_widgets import MDAWidget, StageWidget
from pymmcore_widgets.control._stage_explorer._stage_explorer import StageExplorer

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

# Just in case, clear any previous settings to the default (identity) affine.
cur_group = mmc.getCurrentPixelSizeConfig()
mmc.setPixelSizeAffine(cur_group, [1.0, 0.0, 0.0, 0.0, 1.0, 0.0])

# set camera roi (rectangular helps confirm orientation)
mmc.setROI(0, 0, 512, 256)

explorer = StageExplorer()
explorer.show()

stage_ctrl = StageWidget("XY")
stage_ctrl.setStep(512)
stage_ctrl.snap_checkbox.setChecked(True)
stage_ctrl.show()

mda_widget = MDAWidget()
mda_widget.show()

# v = explorer._stage_viewer

splitter = QSplitter()
splitter.addWidget(explorer)
right = QWidget()
rlayout = QVBoxLayout(right)
rlayout.addWidget(stage_ctrl)
rlayout.addWidget(mda_widget)
splitter.addWidget(right)
splitter.show()

app.exec()
