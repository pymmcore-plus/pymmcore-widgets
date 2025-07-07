from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from pymmcore_plus import DeviceType, Keyword, PropertyType
from typing_extensions import TypeAlias

from pymmcore_widgets._icons import DEVICE_TYPE_ICON, StandardIcon

if TYPE_CHECKING:
    from collections.abc import Hashable

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

    properties: tuple[DevicePropertySetting, ...] = Field(default_factory=tuple)

    @property
    def is_loaded(self) -> bool:
        """Return True if the device is loaded."""
        return bool(self.label)

    @property
    def iconify_key(self) -> str | None:
        """Return an iconify key for the device type."""
        return DEVICE_TYPE_ICON.get(self.type, None)

    def key(self) -> Hashable:
        """Return a unique key for the device."""
        return (self.library, self.name)

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, values: Any) -> Any:
        """Validate the input values."""
        if isinstance(values, str):
            return {"label": values}
        return values


class DevicePropertySetting(_BaseModel):
    """One property on a device."""

    device: Device = Field(..., repr=False, exclude=True)
    property_name: str
    value: str = ""

    is_read_only: bool = Field(default=False, frozen=True)
    is_pre_init: bool = Field(default=False, frozen=True)
    allowed_values: tuple[str, ...] = Field(default_factory=tuple, frozen=True)
    limits: tuple[float, float] | None = Field(default=None, frozen=True)
    property_type: PropertyType = Field(default=PropertyType.Undef, frozen=True)
    sequence_max_length: int = Field(default=0, frozen=True)

    parent: ConfigPreset | None = Field(default=None, exclude=True, repr=False)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def device_label(self) -> str:
        """Return the label of the device."""
        return self.device.label

    @property
    def is_advanced(self) -> bool:
        """Return True if the property is less likely to be needed usually."""
        if self.device.type == DeviceType.State and self.property_name == Keyword.State:
            return True
        return False

    def key(self) -> tuple[str, str]:
        """Return a unique key for the Property."""
        return (self.device_label, self.property_name)

    def as_tuple(self) -> tuple[str, str, str]:
        """Return the property as a tuple."""
        return (self.device_label, self.property_name, self.value)

    @property
    def iconify_key(self) -> StandardIcon | None:
        """Return an iconify key for the device type."""
        if self.is_read_only:
            return StandardIcon.READ_ONLY
        elif self.is_pre_init:
            return StandardIcon.PRE_INIT
        return None

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

    def __eq__(self, other: Any) -> bool:
        # deal with recursive equality checks
        if not isinstance(other, DevicePropertySetting):  # pragma: no cover
            return False
        return (
            self.device_label == other.device_label
            and self.property_name == other.property_name
            and self.value == other.value
            and self.is_read_only == other.is_read_only
            and self.is_pre_init == other.is_pre_init
            and self.allowed_values == other.allowed_values
            and self.limits == other.limits
            and self.property_type == other.property_type
            and self.sequence_max_length == other.sequence_max_length
        )


class ConfigPreset(_BaseModel):
    """Set of settings in a ConfigGroup."""

    name: str
    settings: list[DevicePropertySetting] = Field(default_factory=list)

    parent: ConfigGroup | None = Field(default=None, exclude=True, repr=False)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, ConfigPreset):  # pragma: no cover
            return False
        return self.name == value.name and self.settings == value.settings

    @property
    def is_system_startup(self) -> bool:
        """Return True if the preset is the system startup preset."""
        return (
            self.name.lower() == "startup"
            and self.parent is not None
            and self.parent.is_system_group
        )

    @property
    def is_system_shutdown(self) -> bool:
        """Return True if the preset is the system shutdown preset."""
        return (
            self.name.lower() == "shutdown"
            and self.parent is not None
            and self.parent.is_system_group
        )


class ConfigGroup(_BaseModel):
    """A group of ConfigPresets."""

    name: str
    presets: dict[str, ConfigPreset] = Field(default_factory=dict)

    is_channel_group: bool = False

    @property
    def is_system_group(self) -> bool:
        """Return True if the group is a system group."""
        return self.name.lower() == "system"


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

    is_channel_group: Literal[False] = Field(default=False, frozen=True)


DevicePropertySetting.model_rebuild()
ConfigPreset.model_rebuild()
ConfigGroup.model_rebuild()
PixelSizePreset.model_rebuild()
PixelSizeConfigs.model_rebuild()
