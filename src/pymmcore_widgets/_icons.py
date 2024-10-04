from __future__ import annotations

from fonticon_mdi6 import MDI6
from pymmcore_plus import DeviceType

ICONS: dict[DeviceType, str] = {
    DeviceType.Any: MDI6.devices,
    DeviceType.AutoFocus: MDI6.auto_upload,
    DeviceType.Camera: MDI6.camera,
    DeviceType.Core: MDI6.checkbox_blank_circle_outline,
    DeviceType.Galvo: MDI6.mirror_variant,
    DeviceType.Generic: MDI6.dev_to,
    DeviceType.Hub: MDI6.hubspot,
    DeviceType.ImageProcessor: MDI6.image_auto_adjust,
    DeviceType.Magnifier: MDI6.magnify_plus,
    DeviceType.Shutter: MDI6.camera_iris,
    DeviceType.SignalIO: MDI6.signal,
    DeviceType.SLM: MDI6.view_comfy,
    DeviceType.Stage: MDI6.arrow_up_down,
    DeviceType.State: MDI6.state_machine,
    DeviceType.Unknown: MDI6.dev_to,
    DeviceType.XYStage: MDI6.arrow_all,
    DeviceType.Serial: MDI6.serial_port,
}
