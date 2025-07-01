from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QModelIndex
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigGroupsTree

app = QApplication([])

core = CMMCorePlus()
core.loadSystemConfiguration()

tree = ConfigGroupsTree.create_from_core(core)
tree.show()
tree.expandRecursively(QModelIndex())
tree.resize(600, 600)

app.exec()
