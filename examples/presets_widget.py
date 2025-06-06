"""Example Usage of the PresetsWidget class.

In this example all the available groups created in micromanager
are displayed with a 'PresetsWidget'.
"""

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QFormLayout, QWidget

from pymmcore_widgets import PresetsWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()


class Configs(QWidget):
    """A simple widget to display all available config groups."""

    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        for group in mmc.getAvailableConfigGroups():
            gp_wdg = PresetsWidget(group)
            layout.addRow(f"{group}:", gp_wdg)


configs = Configs()
configs.show()

app.exec()
