from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigGroupsEditor

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration()

# sample config ----------------------------------------------------------
cam_grp = ConfigGroup(
    "Camera",
    presets={
        "Cy5": ConfigPreset(
            name="Cy5",
            settings=[
                Setting("Dichroic", "Label", "400DCLP"),
                Setting("Camera", "Gain", "0"),
                Setting("Core", "Shutter", "White Light Shutter"),
            ],
        ),
        "FITC": ConfigPreset(
            name="FITC",
            settings=[
                Setting("Dichroic", "Label", "400DCLP"),
                Setting("Emission", "Label", "Chroma-HQ620"),
            ],
        ),
    },
)
obj_grp = ConfigGroup("Objective")

w = ConfigGroupsEditor()
w.setData([cam_grp, obj_grp])
w.resize(1200, 600)
w.show()
app.exec()
