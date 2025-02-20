from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import GroupPresetTableWidget, StageWidget
from pymmcore_widgets.control._stage_explorer._stage_explorer_wip import StageExplorer

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
# delete px size affine
mmc.setPixelSizeAffine("Res10x", [1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
mmc.setPixelSizeAffine("Res20x", [1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
mmc.setPixelSizeAffine("Res40x", [1.0, 0.0, 0.0, 0.0, 1.0, 0.0])

# set camera roi
mmc.setROI(0, 0, 512, 256)
# mmc.setROI(0, 0, 256, 512)

wdg = StageExplorer()
wdg.poll_stage_position = True
wdg.scaleChanged.connect(lambda x: print(f"Scale changed to {x}"))


def _print_stage_position():
    print(wdg.value())


wdg.rectChanged.connect(_print_stage_position)

wdg.show()

# stage = StageWidget("XY")
# stage.setStep(512)
# stage.snap_checkbox.setChecked(True)
# stage.show()

# MDA = MDAWidget()
# MDA.show()

# gp = GroupPresetTableWidget()
# gp.show()

v = wdg._stage_viewer
# app.exec()
