"""A set of widgets for the pymmcore-plus module."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pymmcore-widgets")
except PackageNotFoundError:
    __version__ = "uninstalled"

from ._camera_roi_widget import CameraRoiWidget
from ._channel_widget import ChannelWidget
from ._device_widget import DeviceWidget, StateDeviceWidget
from ._exposure_widget import DefaultCameraExposureWidget, ExposureWidget
from ._group_preset_widget._group_preset_table_widget import GroupPresetTableWidget
from ._image_widget import ImagePreview
from ._live_button_widget import LiveButton
from ._load_system_cfg_widget import ConfigurationWidget
from ._mda_widget._mda_widget import MDAWidget
from ._objective_widget import ObjectivesWidget
from ._pixel_size_widget import PixelSizeWidget
from ._presets_widget import PresetsWidget
from ._property_browser import PropertyBrowser
from ._property_widget import PropertyWidget
from ._sample_explorer_widget._sample_explorer_widget import SampleExplorerWidget
from ._shutter_widget import ShuttersWidget
from ._slider_dialog_widget import SliderDialog
from ._snap_button_widget import SnapButton
from ._stage_widget import StageWidget

__all__ = [
    "CameraRoiWidget",
    "ChannelWidget",
    "ConfigurationWidget",
    "DefaultCameraExposureWidget",
    "DeviceWidget",
    "ExposureWidget",
    "MDAWidget",
    "GroupPresetTableWidget",
    "ImagePreview",
    "LiveButton",
    "ObjectivesWidget",
    "PixelSizeWidget",
    "PresetsWidget",
    "PropertyBrowser",
    "PropertyWidget",
    "SampleExplorerWidget",
    "ShuttersWidget",
    "SliderDialog",
    "SnapButton",
    "StageWidget",
    "StateDeviceWidget",
]
