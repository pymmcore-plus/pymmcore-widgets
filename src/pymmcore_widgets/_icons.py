from __future__ import annotations

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

PROPERTY_FLAG_ICON: dict[str, str] = {
    "read-only": "fluent:edit-off-20-regular",
    "pre-init": "mynaui:letter-p-diamond",
}


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
