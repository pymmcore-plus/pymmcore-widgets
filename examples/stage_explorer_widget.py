from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QModelIndex
from qtpy.QtWidgets import QApplication, QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from pymmcore_widgets import (
    CameraRoiWidget,
    GroupPresetTableWidget,
    MDAWidget,
    StageExplorer,
    StageWidget,
)

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

# set camera roi (rectangular helps confirm orientation)
mmc.setROI(0, 0, 600, 400)

xy = mmc.getXYStageDevice()
if mmc.hasProperty(xy, "Velocity"):
    mmc.setProperty(xy, "Velocity", 2)

explorer = StageExplorer()
stage_ctrl = StageWidget(mmc.getXYStageDevice())
stage_ctrl.setStep(512)
stage_ctrl.snap_checkbox.setChecked(True)

z_ctrl = StageWidget(mmc.getFocusDevice())
z_ctrl.snap_checkbox.setChecked(True)

mda_widget = MDAWidget()
group_wdg = GroupPresetTableWidget()
cam_roi = CameraRoiWidget()


# As an example...
# When ROIs are edited or destroyed, update the MDA widget's stage positions.
def _on_data_changed(top_left: QModelIndex, bottom_right: QModelIndex) -> None:
    positions = [roi.create_useq_position() for roi in explorer.roi_manager.all_rois()]
    # optional: skip positions that don't actually have a valid sequence (grid plan)
    positions = [pos for pos in positions if pos.sequence is not None]
    mda_widget.stage_positions.setValue(positions)


model = explorer.roi_manager.roi_model
model.dataChanged.connect(_on_data_changed)
model.rowsRemoved.connect(_on_data_changed)


# layout

splitter = QSplitter()
left = QWidget()
llayout = QVBoxLayout(left)
llayout.addWidget(group_wdg)
llayout.addWidget(cam_roi)
splitter.addWidget(left)
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
