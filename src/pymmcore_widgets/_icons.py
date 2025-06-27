from __future__ import annotations

from pymmcore_plus import DeviceType

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
