# import the necessary packages
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigurationWidget, GroupPresetTableWidget

# create a QApplication
app = QApplication([])

# create a CMMCorePlus instance.
mmc = CMMCorePlus.instance()

# create a ConfigurationWidget
cfg_widget = ConfigurationWidget()

# create a GroupPresetTableWidget
gp_widget = GroupPresetTableWidget()

# show the created widgets
cfg_widget.show()
gp_widget.show()

app.exec()
