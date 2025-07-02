from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, DeviceType

from ._py_config_model import ConfigGroup, ConfigPreset, Device, DevicePropertySetting

if TYPE_CHECKING:
    from collections.abc import Container, Iterable


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
) -> Iterable[DevicePropertySetting]:
    for device, prop, value in core.getConfigData(group, preset):
        prop_model = DevicePropertySetting(
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
            props.append(DevicePropertySetting(device=dev, **prop_info))
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
