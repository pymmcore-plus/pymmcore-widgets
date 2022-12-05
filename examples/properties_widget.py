"""The PropertiesWidget creates a composite widget with controls for

a number of different properties, filtered based on the arguments
to the constructor.
"""
from pymmcore_plus import CMMCorePlus, PropertyType
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import PropertiesWidget

app = QApplication([])

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

wdg = PropertiesWidget(
    # regex pattern to match property names
    property_name_pattern="test",
    property_type={PropertyType.Float},
    has_limits=True,
)

wdg.show()
app.exec_()
