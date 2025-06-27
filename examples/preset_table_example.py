"""
Example showing how to use the ConfigPresetTableWidget.

This widget provides a table view for editing a single ConfigGroup where:
- Columns represent presets in the group
- Rows represent device/property combinations
- Cells show the property values for each preset
"""

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import ConfigGroup
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.config_presets._qmodel._config_model import QConfigGroupsModel
from pymmcore_widgets.config_presets._qmodel._preset_table import (
    ConfigPresetTableWidget,
)

app = QApplication([])

# Initialize core and load config
core = CMMCorePlus()
core.loadSystemConfiguration()

# Create the model
groups = core.getAvailableConfigGroups()
config_groups = [ConfigGroup.create_from_core(core, name) for name in groups]
model = QConfigGroupsModel(config_groups)

# Create main widget
main_widget = QWidget()
layout = QVBoxLayout(main_widget)

# Add group selector
group_layout = QHBoxLayout()
group_layout.addWidget(QLabel("Config Group:"))
group_selector = QComboBox()
group_selector.addItems(groups)
group_layout.addWidget(group_selector)
layout.addLayout(group_layout)

# Create the preset table widget
preset_table = ConfigPresetTableWidget()
preset_table.setModel(model)

if groups:
    preset_table.setCurrentGroup(groups[0])


@group_selector.currentTextChanged.connect
def _on_group_changed(group_name: str):
    preset_table.setCurrentGroup(group_name)


layout.addWidget(preset_table)

# Show the widget
main_widget.resize(800, 600)
main_widget.setWindowTitle("Config Preset Table Example")
main_widget.show()

app.exec()
