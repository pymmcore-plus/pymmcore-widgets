from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymmcore_plus import CMMCorePlus, PropertyType
from typing_extensions import TypeAlias  # py310

if TYPE_CHECKING:
    from collections.abc import Iterable

AffineTuple: TypeAlias = tuple[float, float, float, float, float, float]


class _BaseModel(BaseModel):
    """Base model for configuration presets."""

    model_config: ClassVar = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class DeviceProperty(_BaseModel):
    """One property on a device."""

    device_label: str
    property_name: str
    value: str = ""

    is_read_only: bool = Field(default=False, frozen=True)
    is_pre_init: bool = Field(default=False, frozen=True)
    allowed_values: tuple[str, ...] = Field(default_factory=tuple, frozen=True)
    limits: tuple[float, float] | None = Field(default=None, frozen=True)
    property_type: PropertyType = Field(default=PropertyType.Undef, frozen=True)
    sequence_max_length: int = Field(default=0, frozen=True)

    parent: ConfigPreset | None = None

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


class ConfigPreset(_BaseModel):
    """Set of settings in a ConfigGroup."""

    name: str
    settings: list[DeviceProperty] = Field(default_factory=list)

    parent: ConfigGroup | None = None

    def add_setting(self, setting: DeviceProperty | dict) -> None:
        """Add a setting to the preset."""
        _setting = DeviceProperty.model_validate(setting)
        _setting.parent = self
        self.settings.append(_setting)


class ConfigGroup(_BaseModel):
    """A group of ConfigPresets."""

    name: str
    presets: dict[str, ConfigPreset] = Field(default_factory=dict)

    def add_preset(self, preset: ConfigPreset | dict) -> None:
        """Add a preset to the group."""
        _preset = ConfigPreset.model_validate(preset)
        _preset.parent = self
        self.presets[_preset.name] = _preset


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


def get_config_groups(core: CMMCorePlus) -> Iterable[ConfigGroup]:
    """Get the model for configuration groups."""
    for group in core.getAvailableConfigGroups():
        group_model = ConfigGroup(name=group)
        for preset in core.getAvailableConfigs(group):
            preset_model = ConfigPreset(name=preset)
            for device, prop, value in core.getConfigData(group, preset):
                max_len = 0
                limits = None
                if core.isPropertySequenceable(device, prop):
                    max_len = core.getPropertySequenceMaxLength(device, prop)
                if core.hasPropertyLimits(device, prop):
                    limits = (
                        core.getPropertyLowerLimit(device, prop),
                        core.getPropertyUpperLimit(device, prop),
                    )

                prop_model = DeviceProperty(
                    device_label=device,
                    property_name=prop,
                    value=value,
                    property_type=core.getPropertyType(device, prop),
                    is_read_only=core.isPropertyReadOnly(device, prop),
                    is_pre_init=core.isPropertyPreInit(device, prop),
                    allowed_values=core.getAllowedPropertyValues(device, prop),
                    sequence_max_length=max_len,
                    limits=limits,
                )

                preset_model.add_setting(prop_model)
            group_model.add_preset(preset_model)
        yield group_model
