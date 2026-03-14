from __future__ import annotations

from enum import Enum

from pymmcore_plus import CMMCorePlus, DeviceType, PropertyType
from superqt import QIconifyIcon


class StandardIcon(str, Enum):
    READ_ONLY = "fluent:edit-off-20-regular"
    PRE_INIT = "mynaui:letter-p-diamond"
    EXPAND = "mdi:expand-horizontal"
    COLLAPSE = "mdi:collapse-horizontal"
    TABLE = "mdi:table"
    TREE = "ph:tree-view"
    FOLDER_ADD = "fluent:folder-add-24-regular"
    DOCUMENT_ADD = "fluent:document-add-24-regular"
    PROPERTY_ADD = "fluent:form-new-24-regular"
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
    UNDO = "mdi:undo"
    REDO = "mdi:redo"

    PROP_STRING = "mdi:alphabetical-variant"
    PROP_INTEGER = "mdi:numeric"
    PROP_FLOAT = "mdi:decimal"
    PROP_ENUM = "mdi:format-list-bulleted"
    PROP_BOOLEAN = "mdi:toggle-switch-outline"
    PROP_UNDEF = "mdi:help-circle-outline"

    DEVICE_ANY = "mdi:devices"
    DEVICE_AUTOFOCUS = "mdi:focus-auto"
    DEVICE_CAMERA = "mdi:camera"
    DEVICE_CORE = "mdi:heart-cog-outline"
    DEVICE_GALVO = "mdi:mirror-variant"
    DEVICE_GENERIC = "mdi:dev-to"
    DEVICE_HUB = "mdi:hubspot"
    DEVICE_IMAGEPROCESSOR = "mdi:image-auto-adjust"
    DEVICE_MAGNIFIER = "mdi:magnify"
    DEVICE_SHUTTER = "mdi:camera-iris"
    DEVICE_SIGNALIO = "fa6-solid:wave-square"
    DEVICE_SLM = "mdi:view-comfy"
    DEVICE_STAGE = "mdi:arrow-up-down"
    DEVICE_STATE = "mdi:state-machine"
    DEVICE_UNKNOWN = "mdi:question-mark-rhombus"
    DEVICE_XYSTAGE = "mdi:arrow-all"
    DEVICE_SERIAL = "mdi:serial-port"

    def icon(self, color: str = "gray") -> QIconifyIcon:
        return QIconifyIcon(self.value, color=color)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def for_device_type(cls, device_type: DeviceType | str) -> StandardIcon:
        """Return an icon for a specific device type.

        If a string is provided, it will be resolved to a DeviceType using the
        CMMCorePlus.instance.
        """
        if isinstance(device_type, str):  # device label
            try:
                device_type = CMMCorePlus.instance().getDeviceType(device_type)
            except Exception:  # pragma: no cover
                device_type = DeviceType.Unknown

        return _DEVICE_TYPE_MAP.get(device_type, StandardIcon.DEVICE_UNKNOWN)

    @classmethod
    def for_property_type(
        cls,
        prop_type: PropertyType,
        allowed: tuple[str, ...] = (),
    ) -> StandardIcon:
        """Return an icon for a specific property type."""
        if prop_type is PropertyType.Integer and set(allowed) == {"0", "1"}:
            return StandardIcon.PROP_BOOLEAN
        if allowed:
            return StandardIcon.PROP_ENUM
        return _PROPERTY_TYPE_MAP.get(prop_type, StandardIcon.PROP_UNDEF)


_PROPERTY_TYPE_MAP: dict[PropertyType, StandardIcon] = {
    PropertyType.String: StandardIcon.PROP_STRING,
    PropertyType.Integer: StandardIcon.PROP_INTEGER,
    PropertyType.Float: StandardIcon.PROP_FLOAT,
    PropertyType.Enum: StandardIcon.PROP_ENUM,
    PropertyType.Boolean: StandardIcon.PROP_BOOLEAN,
    PropertyType.Undef: StandardIcon.PROP_UNDEF,
}

_DEVICE_TYPE_MAP: dict[DeviceType, StandardIcon] = {
    DeviceType.Any: StandardIcon.DEVICE_ANY,
    DeviceType.AutoFocus: StandardIcon.DEVICE_AUTOFOCUS,
    DeviceType.Camera: StandardIcon.DEVICE_CAMERA,
    DeviceType.Core: StandardIcon.DEVICE_CORE,
    DeviceType.Galvo: StandardIcon.DEVICE_GALVO,
    DeviceType.Generic: StandardIcon.DEVICE_GENERIC,
    DeviceType.Hub: StandardIcon.DEVICE_HUB,
    DeviceType.ImageProcessor: StandardIcon.DEVICE_IMAGEPROCESSOR,
    DeviceType.Magnifier: StandardIcon.DEVICE_MAGNIFIER,
    DeviceType.Shutter: StandardIcon.DEVICE_SHUTTER,
    DeviceType.SignalIO: StandardIcon.DEVICE_SIGNALIO,
    DeviceType.SLM: StandardIcon.DEVICE_SLM,
    DeviceType.Stage: StandardIcon.DEVICE_STAGE,
    DeviceType.State: StandardIcon.DEVICE_STATE,
    DeviceType.Unknown: StandardIcon.DEVICE_UNKNOWN,
    DeviceType.XYStage: StandardIcon.DEVICE_XYSTAGE,
    DeviceType.Serial: StandardIcon.DEVICE_SERIAL,
}
