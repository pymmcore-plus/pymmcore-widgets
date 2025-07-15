"""Widgets related to configuration groups and presets."""

from ._group_preset_widget._group_preset_table_widget import GroupPresetTableWidget
from ._objectives_pixel_configuration_widget import ObjectivesPixelConfigurationWidget
from ._pixel_configuration_widget import PixelConfigurationWidget
from ._views._config_groups_editor import ConfigGroupsEditor
from ._views._config_groups_tree import ConfigGroupsTree
from ._views._config_presets_table import ConfigPresetsTable
from ._views._group_preset_selector import GroupPresetSelector

__all__ = [
    "ConfigGroupsEditor",
    "ConfigGroupsTree",
    "ConfigPresetsTable",
    "GroupPresetSelector",
    "GroupPresetTableWidget",
    "ObjectivesPixelConfigurationWidget",
    "PixelConfigurationWidget",
]
