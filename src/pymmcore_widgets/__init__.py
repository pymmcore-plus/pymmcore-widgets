"""A set of widgets for the pymmcore-plus module."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pymmcore-widgets")
except PackageNotFoundError:
    __version__ = "uninstalled"

from ._device_widget import DeviceWidget, StateDeviceWidget
from ._exposure_widget import DefaultCameraExposureWidget, ExposureWidget
from ._group_preset_table_widget import GroupPresetTableWidget
from ._live_button_widget import LiveButton
from ._presets_widget import PresetsWidget
from ._property_browser import PropertyBrowser
from ._property_widget import PropertyWidget, make_property_value_widget
from ._snap_button_widget import SnapButton
from ._stage_widget import StageWidget

__all__ = [
    "DeviceWidget",
    "make_property_value_widget",
    "PropertyWidget",
    "StateDeviceWidget",
    "PropertyBrowser",
    "PresetsWidget",
    "ExposureWidget",
    "DefaultCameraExposureWidget",
    "GroupPresetTableWidget",
    "LiveButton",
    "SnapButton",
    "StageWidget",
]
