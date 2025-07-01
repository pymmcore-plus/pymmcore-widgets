from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QModelIndex
from qtpy.QtWidgets import QApplication, QSplitter

from pymmcore_widgets import ConfigGroupsEditor, ConfigGroupsTree

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration()

cfg = ConfigGroupsEditor.create_from_core(core)
cfg.setCurrentPreset("Channel", "FITC")

# right-hand tree view showing the *same* model
tree = ConfigGroupsTree()
tree.setModel(cfg._model)
tree.expandRecursively(QModelIndex())


splitter = QSplitter()
splitter.addWidget(cfg)
splitter.addWidget(tree)
splitter.resize(1400, 800)
splitter.setSizes([900, 500])
splitter.show()

app.exec()
