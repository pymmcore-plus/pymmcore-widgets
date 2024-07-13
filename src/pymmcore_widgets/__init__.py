"""A set of widgets for the pymmcore-plus module."""

import warnings
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pymmcore-widgets")
except PackageNotFoundError:
    __version__ = "uninstalled"

from ._deprecated._device_widget import DeviceWidget, StateDeviceWidget
from ._install_widget import InstallWidget
from .config_presets._group_preset_widget._group_preset_table_widget import (
    GroupPresetTableWidget,
)
from .config_presets._objectives_pixel_configuration_widget import (
    ObjectivesPixelConfigurationWidget,
)
from .config_presets._pixel_configuration_widget import PixelConfigurationWidget
from .control._camera_roi_widget import CameraRoiWidget
from .control._channel_group_widget import ChannelGroupWidget
from .control._channel_widget import ChannelWidget
from .control._exposure_widget import DefaultCameraExposureWidget, ExposureWidget
from .control._live_button_widget import LiveButton
from .control._load_system_cfg_widget import ConfigurationWidget
from .control._objective_widget import ObjectivesWidget
from .control._presets_widget import PresetsWidget
from .control._shutter_widget import ShuttersWidget
from .control._snap_button_widget import SnapButton
from .control._stage_widget import StageWidget
from .device_properties._properties_widget import PropertiesWidget
from .device_properties._property_browser import PropertyBrowser
from .device_properties._property_widget import PropertyWidget
from .hcwizard import ConfigWizard
from .mda import MDAWidget
from .useq_widgets import (
    ChannelTable,
    GridPlanWidget,
    MDASequenceWidget,
    PositionTable,
    TimePlanWidget,
    ZPlanWidget,
)
from .views._image_widget import ImagePreview


def __getattr__(name: str) -> object:
    if name == "ZStackWidget":
        warnings.warn(
            "'ZStackWidget' is deprecated, using 'ZPlanWidget' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return ZPlanWidget
    if name == "GridWidget":
        warnings.warn(
            "'GridWidget' is deprecated, using 'GridPlanWidget' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return GridPlanWidget
    if name == "PixelSizeWidget":
        warnings.warn(
            "PixelSizeWidget is deprecated, "
            "using ObjectivesPixelConfigurationWidget instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return ObjectivesPixelConfigurationWidget
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = [
    "CameraRoiWidget",
    "ChannelGroupWidget",
    "ChannelTable",
    "ChannelWidget",
    "ConfigurationWidget",
    "ConfigWizard",
    "DefaultCameraExposureWidget",
    "DeviceWidget",
    "ExposureWidget",
    "GridPlanWidget",
    "GroupPresetTableWidget",
    "ImagePreview",
    "InstallWidget",
    "LiveButton",
    "MDAWidget",
    "MDASequenceWidget",
    "ObjectivesWidget",
    "ObjectivesPixelConfigurationWidget",
    "PixelConfigurationWidget",
    "PositionTable",
    "PresetsWidget",
    "PropertiesWidget",
    "PropertyBrowser",
    "PropertyWidget",
    "ShuttersWidget",
    "SnapButton",
    "StageWidget",
    "StateDeviceWidget",
    "TimePlanWidget",
    "ZPlanWidget",
]
