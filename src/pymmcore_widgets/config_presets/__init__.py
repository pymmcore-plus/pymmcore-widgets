"""Widgets related to configuration groups and presets."""

from ._group_preset_widget._group_preset_table_widget import GroupPresetTableWidget
from ._objectives_pixel_configuration_widget import ObjectivesPixelConfigurationWidget
from ._pixel_configuration_widget import PixelConfigurationWidget
from ._qmodel._config_model import QConfigGroupsModel

__all__ = [
    "GroupPresetTableWidget",
    "ObjectivesPixelConfigurationWidget",
    "PixelConfigurationWidget",
    "QConfigGroupsModel",
]
