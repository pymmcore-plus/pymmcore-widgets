from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, DeviceType

from pymmcore_widgets._util import block_core

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


def set_config_groups(
    core: CMMCorePlus,
    groups: Sequence[ConfigGroup],
    *,
    deleted_groups: Sequence[str] | None = None,
    channel_group: str | None = None,
) -> None:
    """Update config groups in the core.

    Parameters
    ----------
    core : CMMCorePlus
        The core instance to update.
    groups : Sequence[ConfigGroup]
        Groups to create or update in the core. If a group with the same name
        already exists, it is deleted and recreated.
    deleted_groups : Sequence[str] | None
        If provided, only these group names are deleted from the core
        (incremental mode). If None (default), all existing groups not present
        in *groups* are deleted (full-replacement mode).
    channel_group : str | None
        If provided, set this group as the channel group after applying changes.
        If None and *deleted_groups* is also None (full-replacement mode), the
        channel group is inferred from the ``is_channel_group`` flag on groups.
    """
    if deleted_groups is None:
        desired_names = {g.name for g in groups}
        names_to_delete: list[str] = [
            n for n in core.getAvailableConfigGroups() if n not in desired_names
        ]
    else:
        names_to_delete = list(deleted_groups)

    with block_core(core.events):
        for name in names_to_delete:
            print("Deleting config group:", name)
            core.deleteConfigGroup(name)

        existing = set(core.getAvailableConfigGroups())
        for group in groups:
            if group.name in existing:
                core.deleteConfigGroup(group.name)
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

    # NOTE:
    # I dislike that we're manually emitting signals here, but short of a
    # coalescing mechanism in the core itself, this is the best we can do to
    # minimize extraneous signals
    for name in names_to_delete:
        core.events.configGroupDeleted.emit(name)

    for group in groups:
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

    # Set channel group: explicit parameter takes priority, then fall back to
    # scanning the is_channel_group flag (full-replacement mode only).
    if channel_group is not None:
        core.setChannelGroup(channel_group)
    elif deleted_groups is None:
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
