from __future__ import annotations

from enum import Enum

from pymmcore_plus import CMMCorePlus, DeviceType
from superqt import QIconifyIcon

DEVICE_TYPE_ICON: dict[DeviceType, str] = {
    DeviceType.Any: "mdi:devices",
    DeviceType.AutoFocus: "mdi:focus-auto",
    DeviceType.Camera: "mdi:camera",
    DeviceType.Core: "mdi:heart-cog-outline",
    DeviceType.Galvo: "mdi:mirror-variant",
    DeviceType.Generic: "mdi:dev-to",
    DeviceType.Hub: "mdi:hubspot",
    DeviceType.ImageProcessor: "mdi:image-auto-adjust",
    DeviceType.Magnifier: "mdi:magnify",
    DeviceType.Shutter: "mdi:camera-iris",
    DeviceType.SignalIO: "fa6-solid:wave-square",
    DeviceType.SLM: "mdi:view-comfy",
    DeviceType.Stage: "mdi:arrow-up-down",
    DeviceType.State: "mdi:state-machine",
    DeviceType.Unknown: "mdi:question-mark-rhombus",
    DeviceType.XYStage: "mdi:arrow-all",
    DeviceType.Serial: "mdi:serial-port",
}


class StandardIcon(str, Enum):
    READ_ONLY = "fluent:edit-off-20-regular"
    PRE_INIT = "mynaui:letter-p-diamond"
    EXPAND = "mdi:expand-horizontal"
    COLLAPSE = "mdi:collapse-horizontal"
    TABLE = "mdi:table"
    TREE = "ph:tree-view"
    FOLDER_ADD = "fluent:folder-add-24-regular"
    DOCUMENT_ADD = "fluent:document-add-24-regular"
    DELETE = "fluent:delete-24-regular"
    COPY = "fluent:save-copy-24-regular"
    TRANSPOSE = "carbon:transpose"
    CONFIG_GROUP = "mdi:folder-settings-variant-outline"
    CONFIG_PRESET = "mdi:file-settings-cog-outline"
    HELP = "mdi:help-circle-outline"
    CHANNEL_GROUP = "mynaui:letter-c-waves-solid"
    SYSTEM_GROUP = "mdi:power"
    STARTUP = "ic:baseline-power"
    SHUTDOWN = "ic:baseline-power-off"

    def icon(self, color: str = "gray") -> QIconifyIcon:
        return QIconifyIcon(self.value, color=color)

    def __str__(self) -> str:
        return self.value


def get_device_icon(
    device_type_or_name: DeviceType | str, color: str = "gray"
) -> QIconifyIcon | None:
    if isinstance(device_type_or_name, str):
        try:
            device_type = CMMCorePlus.instance().getDeviceType(device_type_or_name)
        except Exception:
            device_type = DeviceType.Unknown
    else:
        device_type = device_type_or_name
    if icon_string := DEVICE_TYPE_ICON.get(device_type):
        return QIconifyIcon(icon_string, color=color)
    return None
