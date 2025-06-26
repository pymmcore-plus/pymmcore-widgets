from __future__ import annotations

from pymmcore_plus import DeviceType

ICONS: dict[DeviceType, str] = {
    DeviceType.Any: "mdi:devices",
    DeviceType.AutoFocus: "mdi:auto-upload",
    DeviceType.Camera: "mdi:camera",
    DeviceType.Core: "mdi:heart-cog-outline",
    DeviceType.Galvo: "mdi:mirror-variant",
    DeviceType.Generic: "mdi:dev-to",
    DeviceType.Hub: "mdi:hubspot",
    DeviceType.ImageProcessor: "mdi:image-auto-adjust",
    DeviceType.Magnifier: "mdi:magnify-plus",
    DeviceType.Shutter: "mdi:camera-iris",
    DeviceType.SignalIO: "mdi:signal",
    DeviceType.SLM: "mdi:view-comfy",
    DeviceType.Stage: "mdi:arrow-up-down",
    DeviceType.State: "mdi:state-machine",
    DeviceType.Unknown: "mdi:dev-to",
    DeviceType.XYStage: "mdi:arrow-all",
    DeviceType.Serial: "mdi:serial-port",
}
