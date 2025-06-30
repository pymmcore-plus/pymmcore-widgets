from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QModelIndex
from qtpy.QtWidgets import QApplication, QSplitter, QTreeView

from pymmcore_widgets import ConfigGroupsEditor
from pymmcore_widgets.config_presets._qmodel._property_setting_delegate import (
    PropertySettingDelegate,
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
tree.setItemDelegateForColumn(2, PropertySettingDelegate(tree))


splitter = QSplitter()
splitter.addWidget(cfg)
splitter.addWidget(tree)
splitter.resize(1400, 800)
splitter.setSizes([900, 500])
splitter.show()

app.exec()
