from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import StageWidget, GroupPresetTableWidget, MDAWidget
from pymmcore_widgets.control import StageExplorer

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration(r"c:\Users\Admin\dev\Ti_1.cfg")

wdg = StageExplorer()
wdg.poll_stage_position = True
wdg.show()

stage = StageWidget("XYStage")
stage.setStep(512)
stage.snap_checkbox.setChecked(True)
stage.show()

GP = GroupPresetTableWidget()
GP.show()

MDA = MDAWidget()
MDA.show()

app.exec()
