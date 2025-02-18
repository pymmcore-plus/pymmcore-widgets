from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import GroupPresetTableWidget, MDAWidget, StageWidget
from pymmcore_widgets.control import StageExplorer

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

# set camera roi
mmc.setROI(0, 0, 512, 256)
# mmc.setROI(0, 0, 256, 512)

wdg = StageExplorer()
wdg.poll_stage_position = True
wdg.scaleChanged.connect(lambda x: print(f"Scale changed to {x}"))
wdg.show()

stage = StageWidget("XY")
stage.setStep(512)
stage.snap_checkbox.setChecked(True)
stage.show()

MDA = MDAWidget()
MDA.show()

gp = GroupPresetTableWidget()
gp.show()

v = wdg._stage_viewer
app.exec()
