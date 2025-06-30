from __future__ import annotations

from contextlib import suppress

from pymmcore_plus import CMMCorePlus, DeviceType
from superqt import QIconifyIcon

ICONS: dict[DeviceType, str] = {
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
    DeviceType.Unknown: "mdi:dev-to",
    DeviceType.XYStage: "mdi:arrow-all",
    DeviceType.Serial: "mdi:serial-port",
}


def get_device_icon(
    device_type_or_name: DeviceType | str, color: str = "gray"
) -> QIconifyIcon | None:
    if isinstance(device_type_or_name, str):
        with suppress(Exception):
            device_type = CMMCorePlus.instance().getDeviceType(device_type_or_name)
    else:
        device_type = device_type_or_name
    if icon_string := ICONS.get(device_type):
        return QIconifyIcon(icon_string, color=color)
    return None
