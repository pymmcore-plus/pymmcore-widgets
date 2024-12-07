from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import GroupPresetTableWidget, MDAWidget, StageWidget
from pymmcore_widgets.control import StageExplorer

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

wdg = StageExplorer()
wdg.poll_stage_position = True
wdg.show()

stage = StageWidget("XY")
stage.setStep(512)
stage.snap_checkbox.setChecked(True)
stage.show()

MDA = MDAWidget()
MDA.show()

gp = GroupPresetTableWidget()
gp.show()

app.exec()
