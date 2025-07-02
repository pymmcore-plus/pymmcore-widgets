from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymmcore_plus import CMMCorePlus, DeviceType, PropertyType
from typing_extensions import TypeAlias  # py310

if TYPE_CHECKING:
    from collections.abc import Container, Hashable, Iterable

AffineTuple: TypeAlias = tuple[float, float, float, float, float, float]


class _BaseModel(BaseModel):
    """Base model for configuration presets."""

    model_config: ClassVar = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class Device(_BaseModel):
    """A device in the system."""

    label: str = ""  # if empty, the device is not loaded

    name: str = Field(default="", frozen=True)
    library: str = Field(default="", frozen=True)
    description: str = Field(default="", frozen=True)
    type: DeviceType = Field(default=DeviceType.Unknown, frozen=True)

    properties: tuple[DeviceProperty, ...] = Field(default_factory=tuple)

    @property
    def is_loaded(self) -> bool:
        """Return True if the device is loaded."""
        return bool(self.label)

    @property
    def iconify_key(self) -> str | None:
        """Return an iconify key for the device type."""
        from pymmcore_widgets._icons import DEVICE_TYPE_ICON

        return DEVICE_TYPE_ICON.get(self.type, None)

    def key(self) -> Hashable:
        """Return a unique key for the device."""
        return (self.library, self.name)


class DeviceProperty(_BaseModel):
    """One property on a device."""

    device: Device
    property_name: str
    value: str = ""

    is_read_only: bool = Field(default=False, frozen=True)
    is_pre_init: bool = Field(default=False, frozen=True)
    allowed_values: tuple[str, ...] = Field(default_factory=tuple, frozen=True)
    limits: tuple[float, float] | None = Field(default=None, frozen=True)
    property_type: PropertyType = Field(default=PropertyType.Undef, frozen=True)
    sequence_max_length: int = Field(default=0, frozen=True)

    parent: ConfigPreset | None = None

    @property
    def device_label(self) -> str:
        """Return the label of the device."""
        return self.device.label

    def as_tuple(self) -> tuple[str, str, str]:
        """Return the property as a tuple."""
        return (self.device_label, self.property_name, self.value)

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, values: Any) -> Any:
        """Validate the input values."""
        if isinstance(values, (list, tuple)):
            if len(values) == 3:
                return {
                    "device_label": values[0],
                    "property_name": values[1],
                    "value": values[2],
                }
        return values

    def display_name(self) -> str:
        """Return a display name for the property."""
        return f"{self.device_label}-{self.property_name}"


class ConfigPreset(_BaseModel):
    """Set of settings in a ConfigGroup."""

    name: str
    settings: list[DeviceProperty] = Field(default_factory=list)

    parent: ConfigGroup | None = None


class ConfigGroup(_BaseModel):
    """A group of ConfigPresets."""

    name: str
    presets: dict[str, ConfigPreset] = Field(default_factory=dict)


class PixelSizePreset(ConfigPreset):
    """PixelSizePreset model."""

    pixel_size_um: float = 0.0
    affine: AffineTuple = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    dxdz: float = 0.0
    dydz: float = 0.0
    optimalz_um: float = 0.0


class PixelSizeConfigs(ConfigGroup):
    """Model of the pixel size group."""

    name: str = "PixelSizeGroup"
    presets: dict[str, PixelSizePreset] = Field(default_factory=dict)  # type: ignore[assignment]


DeviceProperty.model_rebuild()
ConfigPreset.model_rebuild()
ConfigGroup.model_rebuild()
PixelSizePreset.model_rebuild()
PixelSizeConfigs.model_rebuild()

# ----------------------------------


@cache
def _get_device(core: CMMCorePlus, label: str) -> Device:
    """Get a Device model for the given label."""
    return Device(
        label=label,
        name=core.getDeviceName(label),
        description=core.getDeviceDescription(label),
        library=core.getDeviceLibrary(label),
        type=core.getDeviceType(label),
    )


def get_config_groups(core: CMMCorePlus) -> Iterable[ConfigGroup]:
    """Get the model for configuration groups."""
    for group in core.getAvailableConfigGroups():
        group_model = ConfigGroup(name=group)
        for preset_model in get_config_presets(core, group):
            preset_model.parent = group_model
            group_model.presets[preset_model.name] = preset_model
        yield group_model


def get_config_presets(core: CMMCorePlus, group: str) -> Iterable[ConfigPreset]:
    """Get all available configuration presets for a group."""
    for preset in core.getAvailableConfigs(group):
        preset_model = ConfigPreset(name=preset)
        for prop_model in get_preset_settings(core, group, preset):
            prop_model.parent = preset_model
            preset_model.settings.append(prop_model)
        yield preset_model


def get_preset_settings(
    core: CMMCorePlus, group: str, preset: str
) -> Iterable[DeviceProperty]:
    for device, prop, value in core.getConfigData(group, preset):
        prop_model = DeviceProperty(
            device=_get_device(core, device),
            value=value,
            **get_property_info(core, device, prop),
        )
        yield prop_model


def get_property_info(core: CMMCorePlus, device_label: str, property_name: str) -> dict:
    """Get information about a property of a device.

    Doe *NOT* include the current value of the property.
    """
    max_len = 0
    limits = None
    if core.isPropertySequenceable(device_label, property_name):
        max_len = core.getPropertySequenceMaxLength(device_label, property_name)
    if core.hasPropertyLimits(device_label, property_name):
        limits = (
            core.getPropertyLowerLimit(device_label, property_name),
            core.getPropertyUpperLimit(device_label, property_name),
        )

    return {
        "property_name": property_name,
        "property_type": core.getPropertyType(device_label, property_name),
        "is_read_only": core.isPropertyReadOnly(device_label, property_name),
        "is_pre_init": core.isPropertyPreInit(device_label, property_name),
        "allowed_values": core.getAllowedPropertyValues(device_label, property_name),
        "sequence_max_length": max_len,
        "limits": limits,
    }


def get_loaded_devices(core: CMMCorePlus) -> Iterable[Device]:
    """Get the model for all devices."""
    for label in core.getLoadedDevices():
        dev = Device(
            label=label,
            name=core.getDeviceName(label),
            description=core.getDeviceDescription(label),
            library=core.getDeviceLibrary(label),
            type=core.getDeviceType(label),
        )
        props = []
        for prop in core.getDevicePropertyNames(label):
            prop_info = get_property_info(core, label, prop)
            props.append(DeviceProperty(device=dev, **prop_info))
        dev.properties = tuple(props)
        yield dev


def get_available_devices(
    core: CMMCorePlus, *, exclude: Container[tuple[str, str]] = ()
) -> Iterable[Device]:
    """Get all available devices, not just the loaded ones.

    Use `exclude` to filter out devices that should not be included (e.g. device for
    which you already have information from `get_loaded_devices()`):
    >>> from pymmcore_plus import CMMCorePlus
    >>> core = CMMCorePlus()
    >>> loaded = get_loaded_devices(core)
    >>> available = get_available_devices(core, exclude={dev.key() for dev in loaded})
    """
    for library in core.getDeviceAdapterNames():
        dev_names = core.getAvailableDevices(library)
        types = core.getAvailableDeviceTypes(library)
        descriptions = core.getAvailableDeviceDescriptions(library)
        for dev_name, description, dev_type in zip(dev_names, descriptions, types):
            if (library, dev_name) not in exclude:
                yield Device(
                    name=dev_name,
                    library=library,
                    description=description,
                    type=DeviceType(dev_type),
                )
