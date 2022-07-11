"""A set of widgets for the pymmcore-plus module."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pymmcore-widgets")
except PackageNotFoundError:
    __version__ = "uninstalled"

from ._device_widget import DeviceWidget, StateDeviceWidget
from ._exposure_widget import DefaultCameraExposureWidget, ExposureWidget
from ._load_system_cfg_widget import ConfigurationWidget
from ._presets_widget import PresetsWidget
from ._property_browser import PropertyBrowser, _PropertyTable
from ._property_widget import PropertyWidget, make_property_value_widget

__all__ = [
    "DeviceWidget",
    "make_property_value_widget",
    "PropertyWidget",
    "StateDeviceWidget",
    "PropertyBrowser",
    "_PropertyTable",
    "PresetsWidget",
    "ExposureWidget",
    "DefaultCameraExposureWidget",
    "ConfigurationWidget",
]
