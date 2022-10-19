from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QFormLayout, QWidget

from pymmcore_widgets import PresetsWidget

# In this example all the available groups created in micromanager
# are dysplaied with a 'PresetsWidget'.

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wdg = QWidget()
wdg.setLayout(QFormLayout())

for group in mmc.getAvailableConfigGroups():
    gp_wdg = PresetsWidget(group)
    wdg.layout().addRow(f"{group}:", gp_wdg)

wdg.show()

app.exec_()
