"""Property widgets for device properties.

This module provides widgets for displaying and editing micro-manager device
properties. The main entry point is PropertyWidget, which automatically selects
an appropriate widget based on the property type and constraints.
"""

from __future__ import annotations

import contextlib
from typing import Any, cast

from pymmcore_plus import CMMCorePlus, DeviceType, Keyword, PropertyType
from qtpy.QtCore import QEvent, Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QWidget,
)

STATE = Keyword.State.value
LABEL = Keyword.Label.value

# Large default range for numeric properties without limits.
# Using reasonable bounds that won't cause overflow issues.
DEFAULT_INT_MIN = -(2**31)
DEFAULT_INT_MAX = 2**31 - 1
DEFAULT_FLOAT_MIN = -1e12
DEFAULT_FLOAT_MAX = 1e12


class _WheelBlocker(QWidget):
    """Singleton event filter that blocks wheel events on unfocused widgets."""

    _instance: _WheelBlocker | None = None

    @classmethod
    def instance(cls) -> _WheelBlocker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def eventFilter(self, a0: Any, a1: Any) -> bool:
        if a1.type() == QEvent.Type.Wheel:
            if hasattr(a0, "hasFocus") and not a0.hasFocus():
                a1.ignore()
                return True
        return False


def _block_wheel(widget: QWidget) -> None:
    """Install event filter to block wheel events on an unfocused widget."""
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.installEventFilter(_WheelBlocker.instance())


# ---------------------------------------------------------------------------
# Base widget classes
# ---------------------------------------------------------------------------


class IntSpinBox(QSpinBox):
    """Integer spinbox that validates only on editing finished."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setKeyboardTracking(False)  # Don't emit while typing
        self.setRange(DEFAULT_INT_MIN, DEFAULT_INT_MAX)
        _block_wheel(self)

    def setValue(self, val: int | str) -> None:
        """Set value, accepting strings from core."""
        if isinstance(val, str):
            val = int(float(val))
        super().setValue(val)


class FloatSpinBox(QDoubleSpinBox):
    """Float spinbox that validates only on editing finished."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setKeyboardTracking(False)  # Don't emit while typing
        self.setRange(DEFAULT_FLOAT_MIN, DEFAULT_FLOAT_MAX)
        self.setDecimals(4)
        _block_wheel(self)

    def setValue(self, val: float | str) -> None:
        """Set value, accepting strings from core."""
        if isinstance(val, str):
            val = float(val)
        # Auto-adjust decimals to show value properly
        val_str = f"{val:.10f}".rstrip("0").rstrip(".")
        if "." in val_str:
            dec = len(val_str.split(".")[1])
            if dec > self.decimals():
                self.setDecimals(min(dec, 10))
        super().setValue(val)


class LabeledSlider(QWidget):
    """A slider with an attached spinbox showing the value.

    This is a simple combination of QSlider and QSpinBox/QDoubleSpinBox,
    with proper synchronization between them.
    """

    valueChanged = Signal(object)  # int or float

    def __init__(
        self,
        is_float: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_float = is_float
        self._scale = 1000 if is_float else 1  # For float precision in slider

        self._slider = QSlider(Qt.Orientation.Horizontal)
        _block_wheel(self._slider)

        if is_float:
            self._spinbox: QSpinBox | QDoubleSpinBox = FloatSpinBox()
        else:
            self._spinbox = IntSpinBox()

        self._spinbox.setFixedWidth(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._spinbox)

        # Connect signals
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

        self._updating = False

    def setRange(self, minimum: float, maximum: float) -> None:
        """Set the range for both slider and spinbox."""
        if self._is_float:
            cast("FloatSpinBox", self._spinbox).setRange(minimum, maximum)
            smin, smax = int(minimum * self._scale), int(maximum * self._scale)
            self._slider.setRange(smin, smax)
        else:
            # Core returns floats even for integer properties
            cast("IntSpinBox", self._spinbox).setRange(int(minimum), int(maximum))
            self._slider.setRange(int(minimum), int(maximum))

    def setValue(self, value: float | str) -> None:
        """Set the value."""
        if self._updating:
            return
        self._updating = True
        try:
            # Convert from string if needed (core always returns strings)
            if isinstance(value, str):
                value = float(value) if self._is_float else int(float(value))
            # Clamp to range if needed
            value = max(self._spinbox.minimum(), min(self._spinbox.maximum(), value))
            self._spinbox.setValue(value)
            if self._is_float:
                self._slider.setValue(int(value * self._scale))
            else:
                self._slider.setValue(int(value))
        finally:
            self._updating = False

    def value(self) -> int | float:
        """Get the current value."""
        return self._spinbox.value()  # type: ignore[no-any-return]

    def _on_slider_changed(self, slider_val: int) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            if self._is_float:
                val = slider_val / self._scale
            else:
                val = slider_val
            self._spinbox.setValue(val)
            self.valueChanged.emit(val)
        finally:
            self._updating = False

    def _on_spinbox_changed(self, val: float) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            if self._is_float:
                self._slider.setValue(int(val * self._scale))
            else:
                self._slider.setValue(int(val))
            self.valueChanged.emit(val)
        finally:
            self._updating = False


class ChoiceComboBox(QComboBox):
    """Combobox for properties with allowed values."""

    valueChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.currentTextChanged.connect(self.valueChanged.emit)
        _block_wheel(self)

    def setChoices(self, choices: tuple[str, ...]) -> None:
        """Set the available choices."""
        current = self.currentText()
        self.blockSignals(True)
        self.clear()
        # Sort numerically if possible
        try:
            sorted_choices = sorted(choices, key=float)
        except ValueError:
            sorted_choices = list(choices)
        self.addItems(sorted_choices)
        # Restore previous selection if still valid
        if current in choices:
            self.setCurrentText(current)
        self.blockSignals(False)

    def setValue(self, value: str) -> None:
        """Set the current value."""
        self.setCurrentText(str(value))

    def value(self) -> str:
        """Get the current value."""
        return self.currentText()  # type: ignore[no-any-return]


class BoolCheckBox(QCheckBox):
    """Checkbox for boolean (0/1) properties."""

    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.valueChanged.emit(int(checked))

    def setValue(self, value: str | int) -> None:
        """Set the value (0 or 1)."""
        self.setChecked(bool(int(value)))

    def value(self) -> int:
        """Get the value (0 or 1)."""
        return int(self.isChecked())


class StringLineEdit(QLineEdit):
    """Line edit for string properties, validates on editing finished."""

    valueChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editingFinished.connect(self._on_editing_finished)

    def _on_editing_finished(self) -> None:
        self.valueChanged.emit(self.text())

    def setValue(self, value: str) -> None:
        """Set the value."""
        self.setText(str(value))

    def value(self) -> str:
        """Get the value."""
        return self.text()  # type: ignore[no-any-return]


class ReadOnlyLabel(QLabel):
    """Label for read-only properties."""

    valueChanged = Signal()  # Never emitted, just for interface consistency

    def setValue(self, value: str) -> None:
        """Set the displayed value."""
        self.setText(str(value))

    def value(self) -> str:
        """Get the displayed value."""
        return self.text()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def _get_allowed_values(mmc: CMMCorePlus, device: str, prop: str) -> tuple[str, ...]:
    """Get allowed values for a property, handling state devices specially."""
    if allowed := mmc.getAllowedPropertyValues(device, prop):
        return allowed

    # Special handling for state device Label/State properties
    if mmc.getDeviceType(device) == DeviceType.StateDevice:
        if prop == LABEL:
            return mmc.getStateLabels(device)
        if prop == STATE:
            n_states = mmc.getNumberOfStates(device)
            return tuple(str(i) for i in range(n_states))

    return ()


def create_property_widget(mmc: CMMCorePlus, device: str, prop: str) -> QWidget:
    """Create an appropriate widget for a device property.

    Parameters
    ----------
    mmc : CMMCorePlus
        The micro-manager core instance.
    device : str
        Device label.
    prop : str
        Property name.

    Returns
    -------
    QWidget
        A widget appropriate for the property type.
    """
    ptype = mmc.getPropertyType(device, prop)
    is_readonly = mmc.isPropertyReadOnly(device, prop)
    has_limits = mmc.hasPropertyLimits(device, prop)
    allowed = _get_allowed_values(mmc, device, prop)

    # Read-only: just a label
    if is_readonly:
        return ReadOnlyLabel()

    # Boolean: checkbox for Integer with allowed = {'0', '1'}
    if ptype is PropertyType.Integer and set(allowed) == {"0", "1"}:
        return BoolCheckBox()

    # Enum/Choice: combobox when there are allowed values
    if allowed:
        wdg = ChoiceComboBox()
        wdg.setChoices(allowed)
        return wdg

    # Numeric with limits: slider + spinbox
    if ptype in (PropertyType.Integer, PropertyType.Float) and has_limits:
        lower = mmc.getPropertyLowerLimit(device, prop)
        upper = mmc.getPropertyUpperLimit(device, prop)
        is_float = ptype is PropertyType.Float
        wdg = LabeledSlider(is_float=is_float)
        wdg.setRange(lower, upper)
        return wdg

    # Numeric without limits: just spinbox
    if ptype is PropertyType.Integer:
        return IntSpinBox()
    if ptype is PropertyType.Float:
        return FloatSpinBox()

    # Fallback: string entry
    return StringLineEdit()


# ---------------------------------------------------------------------------
# Main PropertyWidget
# ---------------------------------------------------------------------------


class PropertyWidget(QWidget):
    """Widget to display and control a single device property.

    Parameters
    ----------
    device_label : str
        Device label.
    prop_name : str
        Property name.
    parent : QWidget | None
        Optional parent widget.
    mmcore : CMMCorePlus | None
        Optional core instance. If not provided, uses the global instance.
    connect_core : bool
        If True, widget changes update the core and vice versa.
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        device_label: str,
        prop_name: str,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
        connect_core: bool = True,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._device = device_label
        self._prop = prop_name
        self._connect_core = connect_core

        # Validate device and property exist
        if device_label not in self._mmc.getLoadedDevices():
            raise ValueError(f"Device not loaded: {device_label!r}")
        if not self._mmc.hasProperty(device_label, prop_name):
            names = self._mmc.getDevicePropertyNames(device_label)
            raise ValueError(
                f"Device {device_label!r} has no property {prop_name!r}. "
                f"Available: {names}"
            )

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create the inner widget
        self._inner = create_property_widget(self._mmc, device_label, prop_name)
        layout.addWidget(self._inner)

        # Set initial value
        self._sync_from_core()

        # Connect signals
        if hasattr(self._inner, "valueChanged"):
            self._inner.valueChanged.connect(self._on_widget_changed)

        self._mmc.events.propertyChanged.connect(self._on_core_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_config_loaded)
        self.destroyed.connect(self._disconnect)

        # Handle pre-init properties
        if self._is_pre_init_and_initialized():
            self.setEnabled(False)

    def _is_pre_init_and_initialized(self) -> bool:
        """Check if property is pre-init and device is initialized."""
        if not self._mmc.isPropertyPreInit(self._device, self._prop):
            return False
        if not hasattr(self._mmc, "getDeviceInitializationState"):
            return False
        return bool(self._mmc.getDeviceInitializationState(self._device))

    def _sync_from_core(self) -> None:
        """Update widget value from core."""
        with contextlib.suppress(RuntimeError, ValueError):
            value = self._mmc.getProperty(self._device, self._prop)
            self._inner.setValue(value)

    def _on_widget_changed(self, value: Any) -> None:
        """Handle widget value changes."""
        if self._connect_core:
            try:
                self._mmc.setProperty(self._device, self._prop, value)
            except (RuntimeError, ValueError):
                # Reset to core value on error
                self._sync_from_core()
                return
        self.valueChanged.emit(value)

    def _on_core_changed(self, device: str, prop: str, value: Any) -> None:
        """Handle core property changes."""
        if device == self._device and prop == self._prop:
            self._inner.blockSignals(True)
            self._inner.setValue(value)
            self._inner.blockSignals(False)

    def _on_config_loaded(self) -> None:
        """Handle system configuration reload."""
        # Refresh choices for choice widgets
        if isinstance(self._inner, ChoiceComboBox):
            allowed = _get_allowed_values(self._mmc, self._device, self._prop)
            self._inner.setChoices(allowed)
        self._sync_from_core()

    def _disconnect(self) -> None:
        """Disconnect from core signals."""
        with contextlib.suppress(RuntimeError):
            self._mmc.events.propertyChanged.disconnect(self._on_core_changed)
            self._mmc.events.systemConfigurationLoaded.disconnect(
                self._on_config_loaded
            )

    def value(self) -> Any:
        """Get the current widget value."""
        return self._inner.value()

    def setValue(self, value: Any) -> None:
        """Set the widget value."""
        self._inner.setValue(value)

    def refresh(self) -> None:
        """Force refresh from core."""
        self._inner.blockSignals(True)
        self._sync_from_core()
        self._inner.blockSignals(False)

    def propertyType(self) -> PropertyType:
        """Return the property type."""
        return self._mmc.getPropertyType(self._device, self._prop)

    def deviceType(self) -> DeviceType:
        """Return the device type."""
        return self._mmc.getDeviceType(self._device)

    def isReadOnly(self) -> bool:
        """Return True if the property is read-only."""
        return self._mmc.isPropertyReadOnly(self._device, self._prop)

    def allowedValues(self) -> tuple[str, ...]:
        """Return allowed values if property has constraints."""
        return _get_allowed_values(self._mmc, self._device, self._prop)

    @property
    def _dp(self) -> tuple[str, str]:
        """Return (device, property) tuple."""
        return self._device, self._prop
