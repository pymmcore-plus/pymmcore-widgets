"""A set of widgets for the pymmcore-plus module."""
import warnings
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pymmcore-widgets")
except PackageNotFoundError:
    __version__ = "uninstalled"

from ._camera_roi_widget import CameraRoiWidget
from ._channel_group_widget import ChannelGroupWidget
from ._channel_widget import ChannelWidget
from ._device_widget import DeviceWidget, StateDeviceWidget
from ._exposure_widget import DefaultCameraExposureWidget, ExposureWidget
from ._group_preset_widget._group_preset_table_widget import GroupPresetTableWidget
from ._image_widget import ImagePreview
from ._install_widget import InstallWidget
from ._live_button_widget import LiveButton
from ._load_system_cfg_widget import ConfigurationWidget
from ._objective_widget import ObjectivesWidget
from ._objectives_pixel_configuration_widget import ObjectivesPixelConfigurationWidget
from ._pixel_configuration_widget import PixelConfigurationWidget
from ._presets_widget import PresetsWidget
from ._properties_widget import PropertiesWidget
from ._property_browser import PropertyBrowser
from ._property_widget import PropertyWidget
from ._shutter_widget import ShuttersWidget
from ._snap_button_widget import SnapButton
from ._stage_widget import StageWidget
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
