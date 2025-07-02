"""Widgets related to configuration groups and presets."""

from ._group_preset_widget._group_preset_table_widget import GroupPresetTableWidget
from ._model._q_config_model import QConfigGroupsModel
from ._objectives_pixel_configuration_widget import ObjectivesPixelConfigurationWidget
from ._pixel_configuration_widget import PixelConfigurationWidget
from ._views._config_groups_tree import ConfigGroupsTree
from ._views._config_presets_table import ConfigPresetsTable
from ._views._config_views import ConfigGroupsEditor

__all__ = [
    "ConfigGroupsEditor",
    "ConfigGroupsTree",
    "ConfigPresetsTable",
    "GroupPresetTableWidget",
    "ObjectivesPixelConfigurationWidget",
    "PixelConfigurationWidget",
    "QConfigGroupsModel",
]
