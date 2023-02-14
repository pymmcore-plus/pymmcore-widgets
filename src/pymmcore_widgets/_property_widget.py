from __future__ import annotations

import contextlib
from typing import Any, Callable, Protocol, TypeVar, cast

import pymmcore
from pymmcore_plus import CMMCorePlus, DeviceType, PropertyType
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)
from superqt import QLabeledDoubleSlider, QLabeledSlider, utils

STATE = pymmcore.g_Keyword_State
LABEL = pymmcore.g_Keyword_Label


# fmt: off
class PSignalInstance(Protocol):
    """The protocol expected of a signal instance."""

    def connect(self, callback: Callable) -> Callable: ...
    def disconnect(self, callback: Callable) -> None: ...
    def emit(self, *args: Any) -> None: ...


class PPropValueWidget(Protocol):
    """The protocol expected of a ValueWidget."""

    valueChanged: PSignalInstance
    destroyed: PSignalInstance
    def value(self) -> str | float: ...
    def setValue(self, val: str | float) -> None: ...
    def setEnabled(self, enabled: bool) -> None: ...
    def setParent(self, parent: QWidget | None) -> None: ...
    def deleteLater(self) -> None: ...
# fmt: on


# -----------------------------------------------------------------------
# These widgets all implement PPropValueWidget for various PropertyTypes.
# -----------------------------------------------------------------------

T = TypeVar("T", bound=float)


def _stretch_range_to_contain(wdg: QLabeledDoubleSlider, val: T) -> T:
    """Set range of `wdg` to include `val`."""
    if val > wdg.maximum():
        wdg.setMaximum(val)
    if val < wdg.minimum():
        wdg.setMinimum(val)
    return val


class IntegerWidget(QSpinBox):
    """Slider suited to managing integer values."""

    def setValue(self, v: Any) -> None:
        return super().setValue(  # type: ignore [no-any-return]
            _stretch_range_to_contain(self, int(v))
        )


class FloatWidget(QDoubleSpinBox):
    """Slider suited to managing float values."""

    def setValue(self, v: Any) -> None:
        # stretch decimals to fit value
        dec = min(str(v).rstrip("0")[::-1].find("."), 8)
        if dec > self.decimals():
            self.setDecimals(dec)
        return super().setValue(  # type: ignore [no-any-return]
            _stretch_range_to_contain(self, float(v))
        )


class _RangedMixin:
    _cast: type[int] | type[float] = float

    # prefer horizontal orientation
    def __init__(  # type: ignore
        self, orientation=Qt.Orientation.Horizontal, parent: QWidget | None = None
    ) -> None:
        super().__init__(orientation, parent)  # type: ignore

    def setValue(self, v: float) -> None:
        val = _stretch_range_to_contain(self, self._cast(v))
        return super().setValue(val)  # type: ignore


class RangedIntegerWidget(_RangedMixin, QLabeledSlider):
    """Slider suited to managing ranged integer values."""

    _cast = int


class RangedFloatWidget(_RangedMixin, QLabeledDoubleSlider):
    """Slider suited to managing ranged float values."""


class IntBoolWidget(QCheckBox):
    """Checkbox for boolean values, which are integers in pymmcore."""

    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.toggled.connect(self._emit)

    def _emit(self, state: bool) -> None:
        self.valueChanged.emit(int(state))

    def value(self) -> int:
        """Get value."""
        return int(self.isChecked())

    def setValue(self, val: str | int) -> None:
        """Set value."""
        return self.setChecked(bool(int(val)))  # type: ignore [no-any-return]


class ChoiceWidget(QComboBox):
    """Combobox for props with a set of allowed values."""

    valueChanged = Signal(str)

    def __init__(
        self, mmcore: CMMCorePlus, dev: str, prop: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore
        self._dev = dev
        self._prop = prop
        self._allowed: tuple[str, ...] = ()

        self._mmc.events.systemConfigurationLoaded.connect(self._refresh_choices)
        self.currentTextChanged.connect(self.valueChanged.emit)
        self.destroyed.connect(self._disconnect)
        self._refresh_choices()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._refresh_choices)

    def _refresh_choices(self) -> None:
        with utils.signals_blocked(self):
            self.clear()
            self._allowed = self._get_allowed()
            self.addItems(self._allowed)

    def _get_allowed(self) -> tuple[str, ...]:
        if allowed := self._mmc.getAllowedPropertyValues(self._dev, self._prop):
            return allowed
        if self._mmc.getDeviceType(self._dev) == DeviceType.StateDevice:
            if self._prop == LABEL:
                return self._mmc.getStateLabels(self._dev)
            if self._prop == STATE:
                n_states = self._mmc.getNumberOfStates(self._dev)
                return tuple(str(i) for i in range(n_states))
        return ()

    def value(self) -> str:
        """Get value."""
        return self.currentText()  # type: ignore [no-any-return]

    def setValue(self, value: str) -> None:
        # sourcery skip: remove-unnecessary-cast
        """Set current value."""
        value = str(value)
        # while nice in theory, this check raises unnecessarily when a propertyChanged
        # signal gets emitted during system config loading...
        # if value not in self._allowed:
        #     raise ValueError(f"{value!r} must be one of {self._allowed}")
        self.setCurrentText(value)


class StringWidget(QLineEdit):
    """String widget for pretty much everything else."""

    valueChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editingFinished.connect(self._emit_value)

    def value(self) -> str:
        """Get value."""
        return self.text()  # type: ignore [no-any-return]

    def _emit_value(self) -> None:
        self.valueChanged.emit(self.value())

    def setValue(self, value: str) -> None:
        """Set current value."""
        self.setText(value)
        self._emit_value()


class ReadOnlyWidget(QLabel):
    """String widget for pretty much everything else."""

    valueChanged = Signal()  # just for the protocol... not used

    def value(self) -> str:
        """Get value."""
        return self.text()  # type: ignore [no-any-return]

    def setValue(self, value: str) -> None:
        """Set value."""
        self.setText(value)


# -----------------------------------------------------------------------
# Factory function to create the appropriate PPropValueWidget.
# -----------------------------------------------------------------------


def _creat_prop_widget(mmcore: CMMCorePlus, dev: str, prop: str) -> PPropValueWidget:
    """The type -> widget selection part used in the above function."""
    if mmcore.isPropertyReadOnly(dev, prop):
        return ReadOnlyWidget()

    ptype = mmcore.getPropertyType(dev, prop)
    if allowed := mmcore.getAllowedPropertyValues(dev, prop):
        if ptype is PropertyType.Integer and set(allowed) == {"0", "1"}:
            return IntBoolWidget()
        return ChoiceWidget(mmcore, dev, prop)
    if prop in {STATE, LABEL} and mmcore.getDeviceType(dev) == DeviceType.StateDevice:
        # TODO: This logic is very similar to StateDeviceWidget. use this in the future?
        return ChoiceWidget(mmcore, dev, prop)
    if ptype in (PropertyType.Integer, PropertyType.Float):
        if not mmcore.hasPropertyLimits(dev, prop):
            return IntegerWidget() if ptype is PropertyType.Integer else FloatWidget()
        wdg = (
            RangedIntegerWidget()
            if ptype is PropertyType.Integer
            else RangedFloatWidget()
        )
        wdg.setMinimum(wdg._cast(mmcore.getPropertyLowerLimit(dev, prop)))
        wdg.setMaximum(wdg._cast(mmcore.getPropertyUpperLimit(dev, prop)))
        return wdg
    return cast(PPropValueWidget, StringWidget())


# -----------------------------------------------------------------------
# Main public facing QWidget.
# -----------------------------------------------------------------------


class PropertyWidget(QWidget):
    """A widget to display and control a specified mmcore device property.

    Parameters
    ----------
    device_label : str
        Device label
    prop_name : str
        Property name
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].

    Raises
    ------
    ValueError
        If the `device_label` is not loaded, or does not have a property `prop_name`.
    """

    _value_widget: PPropValueWidget
    valueChanged = Signal(object)

    def __init__(
        self,
        device_label: str,
        prop_name: str,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        if device_label not in self._mmc.getLoadedDevices():
            raise ValueError(f"Device not loaded: {device_label!r}")

        if not self._mmc.hasProperty(device_label, prop_name):
            names = self._mmc.getDevicePropertyNames(device_label)
            raise ValueError(
                f"Device {device_label!r} has no property {prop_name!r}. "
                f"Availble property names include: {names}"
            )

        self._updates_core: bool = True  # whether to update the core on value change
        self._device_label = device_label
        self._prop_name = prop_name

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        # Create the widget based on property type and allowed choices
        self._value_widget = _creat_prop_widget(self._mmc, device_label, prop_name)
        # set current value from core
        self._value_widget.setValue(self._mmc.getProperty(device_label, prop_name))
        self._mmc.events.propertyChanged.connect(self._on_core_change)
        self._value_widget.valueChanged.connect(self._on_value_widget_change)

        self.layout().addWidget(cast(QWidget, self._value_widget))
        self.destroyed.connect(self._disconnect)

    # connect events and queue for disconnection on widget destroyed
    def _on_core_change(self, dev_label: str, prop_name: str, new_val: Any) -> None:
        if dev_label == self._device_label and prop_name == self._prop_name:
            with utils.signals_blocked(self._value_widget):
                self._value_widget.setValue(new_val)

    def _on_value_widget_change(self, value: Any) -> None:
        if not self._updates_core:
            return
        try:
            self._mmc.setProperty(self._device_label, self._prop_name, value)
        except (RuntimeError, ValueError):
            # if there's an error when updating mmcore, reset widget value to mmcore
            real_value = self._mmc.getProperty(self._device_label, self._prop_name)
            self._value_widget.setValue(real_value)

    def _disconnect(self) -> None:
        with contextlib.suppress(RuntimeError):
            self._mmc.events.propertyChanged.disconnect(self._on_core_change)

    def value(self) -> Any:
        """Get value.

        Return the current value of the *widget* (which should match mmcore).
        """
        return self._value_widget.value()

    def connectCore(self, mmcore: CMMCorePlus | None = None) -> None:
        """Connect to core.

        Connect the widget to the core. This is the default state.
        """
        self._updates_core = True
        if mmcore is not None and mmcore is not self._mmc:
            self._mmc = mmcore

    def disconnectCore(self) -> None:
        """Disconnect from core.

        Disconnect the widget from the core. This will prevent the widget
        from updating the core when the value changes.
        """
        self._updates_core = False

    def setValue(self, value: Any) -> None:
        """Set the current value of the *widget* (which should match mmcore)."""
        self._value_widget.setValue(value)

    def allowedValues(self) -> tuple[str, ...]:
        """Return tuple of allowable values if property is categorical."""
        # this will have already been grabbed from mmcore on creation, and will
        # have also taken into account the restrictions in the State/Label property
        # of state devices.  So check for the _allowed attribute on the widget.
        return tuple(getattr(self._value_widget, "_allowed", ()))

    def refresh(self) -> None:
        """Update the value of the widget from mmcore.

        (If all goes well this shouldn't be necessary, but if a propertyChanged
        event is missed, this can be used).
        """
        with utils.signals_blocked(self._value_widget):
            self._value_widget.setValue(self._mmc.getProperty(*self._dp))

    def propertyType(self) -> PropertyType:
        """Return property type."""
        return self._mmc.getPropertyType(*self._dp)

    def deviceType(self) -> DeviceType:
        """Return property type."""
        return self._mmc.getDeviceType(self._device_label)

    def isReadOnly(self) -> bool:
        """Return True if property is read only."""
        return self._mmc.isPropertyReadOnly(*self._dp)

    @property
    def _dp(self) -> tuple[str, str]:
        """Commonly requested pair for mmcore calls."""
        return self._device_label, self._prop_name
