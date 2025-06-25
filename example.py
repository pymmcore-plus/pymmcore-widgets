from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from qtpy.QtWidgets import QApplication, QHBoxLayout, QTreeView, QWidget

from pymmcore_widgets import ConfigGroupsEditor
from pymmcore_widgets.config_presets._qmodel._config_views import SettingValueDelegate

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

cfg = ConfigGroupsEditor()
cfg.setData([cam_grp, obj_grp])

# right-hand tree view showing the *same* model
tree = QTreeView()
tree.setModel(cfg._model)
tree.setColumnWidth(0, 160)  # column 0 (Name) width
# column 2 (Value) uses a line-edit when editing a Setting
tree.setItemDelegateForColumn(2, SettingValueDelegate(tree))


w = QWidget()
layout = QHBoxLayout(w)
layout.addWidget(cfg)
layout.addWidget(tree)
w.resize(1400, 800)
w.show()

app.exec()
