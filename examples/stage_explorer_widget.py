from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from pymmcore_widgets import GroupPresetTableWidget, MDAWidget, StageWidget
from pymmcore_widgets.control._stage_explorer._stage_explorer import StageExplorer

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

# set camera roi (rectangular helps confirm orientation)
mmc.setROI(0, 0, 400, 500)


explorer = StageExplorer()

stage_ctrl = StageWidget(mmc.getXYStageDevice())
stage_ctrl.setStep(512)
stage_ctrl.snap_checkbox.setChecked(True)

z_ctrl = StageWidget(mmc.getFocusDevice())
z_ctrl.snap_checkbox.setChecked(True)

mda_widget = MDAWidget()

group_wdg = GroupPresetTableWidget()
splitter = QSplitter()
splitter.addWidget(group_wdg)
splitter.addWidget(explorer)
right = QWidget()
rlayout = QVBoxLayout(right)
rtop = QHBoxLayout()
rtop.addWidget(stage_ctrl)
rtop.addWidget(z_ctrl)
rlayout.addLayout(rtop)
rlayout.addWidget(mda_widget)
splitter.addWidget(right)
splitter.show()

app.exec()
