"""Property widgets for device properties.

This module provides widgets for displaying and editing micro-manager device
properties. The main entry point is PropertyWidget, which automatically selects
an appropriate widget based on the property type and constraints.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, cast

from pymmcore_plus import (
    CMMCorePlus,
    DeviceInitializationState,
    DeviceType,
    Keyword,
    PropertyType,
)
from qtpy.QtCore import QEvent, QObject, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
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

if TYPE_CHECKING:
    from collections.abc import Iterator

    class PPropValueWidget(QWidget):
        """The protocol expected of a ValueWidget."""

        valueChanged = Signal()

        def value(self) -> str | float: ...
        def setValue(self, val: str | float) -> None: ...
        def setEnabled(self, enabled: bool) -> None: ...
        def deleteLater(self) -> None: ...


STATE = Keyword.State.value
LABEL = Keyword.Label.value

# Large default range for numeric properties without limits.
# Using reasonable bounds that won't cause overflow issues.
DEFAULT_INT_MIN = -(2**31)
DEFAULT_INT_MAX = 2**31 - 1
DEFAULT_FLOAT_MIN = -1e12
DEFAULT_FLOAT_MAX = 1e12


class _WheelBlocker(QObject):
    """Event filter that blocks wheel events on unfocused widgets."""

    def eventFilter(self, a0: Any, a1: Any) -> bool:
        if a1.type() == QEvent.Type.Wheel:
            if hasattr(a0, "hasFocus") and not a0.hasFocus():
                a1.ignore()
                return True
        return False


def _block_wheel(widget: QWidget) -> None:
    """Install event filter to block wheel events on an unfocused widget."""
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget._wheel_blocker = blocker = _WheelBlocker(widget)  # parent to widget
    widget.installEventFilter(blocker)


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

    def textFromValue(self, v: float) -> str:
        # Format with precision, strip trailing zeros
        text = f"{v:.{self.decimals()}f}".rstrip("0").rstrip(".")
        return text

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


@contextlib.contextmanager
def _update_blocker(obj: Any) -> Iterator[None]:
    if obj._updating:
        yield
        return
    obj._updating = True
    try:
        yield
    finally:
        obj._updating = False


class LabeledSlider(QWidget):
    """A slider with an attached spinbox showing the value.

    This is a simple combination of QSlider and QSpinBox/QDoubleSpinBox,
    with proper synchronization between them.
    """

    valueChanged = Signal(object)  # int or float
    _INT32_MAX = 2**31 - 1

    def __init__(
        self,
        is_float: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_float = is_float
        self._scale = 1.0  # Calculated in setRange for floats

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        _block_wheel(self._slider)

        if is_float:
            self._spinbox: QSpinBox | QDoubleSpinBox = FloatSpinBox(self)
        else:
            self._spinbox = IntSpinBox(self)

        # get width of '888888.8888' from font metrics for consistent sizing
        fm = self._spinbox.fontMetrics()
        width = fm.horizontalAdvance("888888.8888") + 2  # + some padding
        self._spinbox.setFixedWidth(width)
        self._spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

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
            # Calculate scale to fit within int32 while maximizing slider precision
            max_abs = max(abs(minimum), abs(maximum), 1e-10)
            self._scale = min(10000.0, self._INT32_MAX / max_abs)
            smin, smax = int(minimum * self._scale), int(maximum * self._scale)
            self._slider.setRange(smin, smax)
        else:
            # Core returns floats even for integer properties
            cast("IntSpinBox", self._spinbox).setRange(int(minimum), int(maximum))
            self._slider.setRange(int(minimum), int(maximum))

    def setValue(self, value: float | str) -> None:
        """Set the value."""
        with _update_blocker(self):
            # Convert from string (core always returns strings)
            value = float(value) if self._is_float else int(float(value))
            self._spinbox.setValue(value)  # pyright: ignore
            if self._is_float:
                self._slider.setValue(int(value * self._scale))
            else:
                self._slider.setValue(value)

    def value(self) -> int | float:
        """Get the current value."""
        return self._spinbox.value()  # type: ignore[no-any-return]

    def _on_slider_changed(self, slider_val: int) -> None:
        with _update_blocker(self):
            if self._is_float:
                val = slider_val / self._scale
            else:
                val = slider_val
            self._spinbox.setValue(val)
            self.valueChanged.emit(val)

    def _on_spinbox_changed(self, val: float) -> None:
        with _update_blocker(self):
            if self._is_float:
                self._slider.setValue(int(val * self._scale))
            else:
                self._slider.setValue(val)
            self.valueChanged.emit(val)


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
        try:
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
        finally:
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


def create_inner_property_widget(
    mmc: CMMCorePlus, device: str, prop: str
) -> PPropValueWidget:
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
    # Read-only: just a label
    if mmc.isPropertyReadOnly(device, prop):
        return cast("PPropValueWidget", ReadOnlyLabel())

    ptype = mmc.getPropertyType(device, prop)
    allowed = _get_allowed_values(mmc, device, prop)

    # Boolean: checkbox for Integer with allowed = {'0', '1'}
    if ptype is PropertyType.Integer and set(allowed) == {"0", "1"}:
        return cast("PPropValueWidget", BoolCheckBox())

    # Enum/Choice: combobox when there are allowed values
    if allowed:
        wdg = ChoiceComboBox()
        wdg.setChoices(allowed)
        return cast("PPropValueWidget", wdg)

    # Numeric with limits: slider + spinbox
    has_limits = mmc.hasPropertyLimits(device, prop)
    if ptype in (PropertyType.Integer, PropertyType.Float) and has_limits:
        lower = mmc.getPropertyLowerLimit(device, prop)
        upper = mmc.getPropertyUpperLimit(device, prop)
        is_float = ptype is PropertyType.Float
        wdg = LabeledSlider(is_float=is_float)
        wdg.setRange(lower, upper)
        return cast("PPropValueWidget", wdg)

    # Numeric without limits: just spinbox
    if ptype is PropertyType.Integer:
        return cast("PPropValueWidget", IntSpinBox())
    if ptype is PropertyType.Float:
        return cast("PPropValueWidget", FloatSpinBox())

    # Fallback: string entry
    return cast("PPropValueWidget", StringLineEdit())


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

        # Create the inner widget
        self._inner = create_inner_property_widget(self._mmc, device_label, prop_name)

        # Set initial value
        self._try_update_from_core()

        self._inner.valueChanged.connect(self._on_widget_changed)
        self._mmc.events.propertyChanged.connect(self._on_core_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_config_loaded)

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._inner)

    # Public methods -----------------------------------------------------

    def value(self) -> Any:
        """Get the current widget value."""
        return self._inner.value()

    def setValue(self, value: Any) -> None:
        """Set the widget value."""
        self._inner.setValue(value)

    def refresh(self) -> None:
        """Update the value of the widget from mmcore.

        (If all goes well this shouldn't be necessary, but if a propertyChanged
        event is missed, this can be used).
        """
        self._inner.blockSignals(True)
        try:
            self._try_update_from_core()
        finally:
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

    # Private methods ----------------------------------------------------

    def _is_pre_init_and_initialized(self) -> bool:
        """Check if property is pre-init and device is initialized."""
        return bool(
            self._mmc.isPropertyPreInit(self._device, self._prop)
            and hasattr(self._mmc, "getDeviceInitializationState")
            and self._mmc.getDeviceInitializationState(self._device)
            != DeviceInitializationState.Uninitialized
        )

    def _try_update_from_core(self) -> Any:
        """Update widget value from core."""
        value = ""
        with contextlib.suppress(RuntimeError, ValueError):
            value = self._mmc.getProperty(self._device, self._prop)
            self._inner.setValue(value)

        # disable for any device init state besides 0 (Uninitialized)
        if self._is_pre_init_and_initialized():
            self.setEnabled(False)

        return value

    def _on_widget_changed(self, value: Any) -> None:
        """Handle widget value changes."""
        if self._connect_core:
            try:
                self._mmc.setProperty(self._device, self._prop, value)
            except (RuntimeError, ValueError):
                # Reset to core value on error
                value = self._try_update_from_core()
        self.valueChanged.emit(value)

    def _on_core_changed(self, device: str, prop: str, value: Any) -> None:
        """Handle core property changes."""
        if device == self._device and prop == self._prop:
            self._inner.blockSignals(True)
            try:
                self._inner.setValue(value)
            finally:
                self._inner.blockSignals(False)

    def _on_config_loaded(self) -> None:
        """Handle system configuration reload."""
        # Refresh choices for choice widgets
        if isinstance(self._inner, ChoiceComboBox):
            allowed = _get_allowed_values(self._mmc, self._device, self._prop)
            self._inner.setChoices(allowed)
        self._try_update_from_core()
