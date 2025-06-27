from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QModelIndex
from qtpy.QtWidgets import QApplication, QHBoxLayout, QTreeView, QWidget

from pymmcore_widgets import ConfigGroupsEditor
from pymmcore_widgets.config_presets._qmodel._property_value_delegate import (
    PropertyValueDelegate,
)

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration()

cfg = ConfigGroupsEditor.create_from_core(core)
cfg.setCurrentPreset("Channel", "FITC")

# right-hand tree view showing the *same* model
tree = QTreeView()
tree.setModel(cfg._model)
tree.expandRecursively(QModelIndex())
tree.setColumnWidth(0, 180)
# make values in in the tree editable
tree.setItemDelegateForColumn(2, PropertyValueDelegate(tree))


w = QWidget()
layout = QHBoxLayout(w)
layout.addWidget(cfg)
layout.addWidget(tree)
w.resize(1400, 800)
w.show()

app.exec()
