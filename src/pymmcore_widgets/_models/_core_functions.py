from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, DeviceType

from ._py_config_model import ConfigGroup, ConfigPreset, Device, DevicePropertySetting

if TYPE_CHECKING:
    from collections.abc import Container, Iterable, Sequence


# ----------------------------------


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
    channel_group = core.getChannelGroup()
    for group in core.getAvailableConfigGroups():
        group_model = ConfigGroup(name=group, is_channel_group=(group == channel_group))
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


def set_config_groups(core: CMMCorePlus, groups: Sequence[ConfigGroup]) -> None:
    """Replace all config groups in the core with the given groups.

    Deletes every existing config group, then re-defines each group/preset/setting.
    Signals are blocked during bulk definition and a single ``configDefined`` is
    emitted per group.  The channel group designation is restored afterwards.
    """
    from pymmcore_widgets._util import block_core

    for group_name in core.getAvailableConfigGroups():
        core.deleteConfigGroup(group_name)

    for group in groups:
        with block_core(core.events):
            if not group.presets:
                core.defineConfigGroup(group.name)
            for preset in group.presets.values():
                for setting in preset.settings:
                    core.defineConfig(
                        group.name,
                        preset.name,
                        setting.device_label,
                        setting.property_name,
                        setting.value,
                    )
        # Emit once per group so listeners can react without being flooded.
        if group.presets:
            last_preset = next(reversed(group.presets.values()))
            if last_preset.settings:
                s = last_preset.settings[-1]
                core.events.configDefined.emit(
                    group.name,
                    last_preset.name,
                    s.device_label,
                    s.property_name,
                    s.value,
                )

    for group in groups:
        if group.is_channel_group:
            core.setChannelGroup(group.name)
            break


def get_loaded_devices(core: CMMCorePlus) -> Iterable[Device]:
    """Get the model for all devices."""
    for label in core.getLoadedDevices():
        dev = _get_device(core, label)
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
        for dev_name, description, dev_type in zip(
            dev_names, descriptions, types, strict=False
        ):
            if (library, dev_name) not in exclude:
                yield Device(
                    name=dev_name,
                    library=library,
                    description=description,
                    type=DeviceType(dev_type),
                )
