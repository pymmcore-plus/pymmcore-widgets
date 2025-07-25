"""A set of widgets for the pymmcore-plus module."""

import warnings
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

try:
    __version__ = version("pymmcore-widgets")
except PackageNotFoundError:
    __version__ = "uninstalled"

__all__ = [
    "CameraRoiWidget",
    "ChannelGroupWidget",
    "ChannelTable",
    "ChannelWidget",
    "ConfigGroupsTree",
    "ConfigWizard",
    "ConfigurationWidget",
    "CoreLogWidget",
    "DefaultCameraExposureWidget",
    "DeviceWidget",
    "ExposureWidget",
    "GridPlanWidget",
    "GroupPresetTableWidget",
    "HCSWizard",
    "ImagePreview",
    "InstallWidget",
    "LiveButton",
    "MDASequenceWidget",
    "MDAWidget",
    "ObjectivesPixelConfigurationWidget",
    "ObjectivesWidget",
    "PixelConfigurationWidget",
    "PositionTable",
    "PresetsWidget",
    "PropertiesWidget",
    "PropertyBrowser",
    "PropertyWidget",
    "ShuttersWidget",
    "SnapButton",
    "StageExplorer",
    "StageWidget",
    "StateDeviceWidget",
    "TimePlanWidget",
    "ZPlanWidget",
]

from ._install_widget import InstallWidget
from ._log import CoreLogWidget
from .config_presets import (
    ConfigGroupsTree,
    GroupPresetTableWidget,
    ObjectivesPixelConfigurationWidget,
    PixelConfigurationWidget,
)
from .control import (
    CameraRoiWidget,
    ChannelGroupWidget,
    ChannelWidget,
    ConfigurationWidget,
    DefaultCameraExposureWidget,
    ExposureWidget,
    LiveButton,
    ObjectivesWidget,
    PresetsWidget,
    ShuttersWidget,
    SnapButton,
    StageExplorer,
    StageWidget,
)
from .device_properties import PropertiesWidget, PropertyBrowser, PropertyWidget
from .hcs import HCSWizard
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
from .views import ImagePreview

if TYPE_CHECKING:
    from ._deprecated._device_widget import (
        DeviceWidget,
        StateDeviceWidget,
    )


def __getattr__(name: str) -> object:
    if name == "DeviceWidget":
        warnings.warn(
            "'DeviceWidget' is deprecated, please seek alternatives.",
            DeprecationWarning,
            stacklevel=2,
        )
        from ._deprecated._device_widget import DeviceWidget

        return DeviceWidget
    if name == "StateDeviceWidget":
        warnings.warn(
            "'StateDeviceWidget' is deprecated, please seek alternatives.",
            DeprecationWarning,
            stacklevel=2,
        )
        from ._deprecated._device_widget import StateDeviceWidget

        return StateDeviceWidget

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
