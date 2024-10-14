"""Widgets related to configuration groups and presets."""

from ._config_groups_editor import ConfigGroupsEditor
from ._group_preset_widget._group_preset_table_widget import GroupPresetTableWidget
from ._objectives_pixel_configuration_widget import ObjectivesPixelConfigurationWidget
from ._pixel_configuration_widget import PixelConfigurationWidget

__all__ = [
    "GroupPresetTableWidget",
    "ObjectivesPixelConfigurationWidget",
    "PixelConfigurationWidget",
    "ConfigGroupsEditor",
]
