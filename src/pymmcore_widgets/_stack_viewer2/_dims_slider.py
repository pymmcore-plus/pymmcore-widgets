from __future__ import annotations

from typing import TYPE_CHECKING, Any
from warnings import warn

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from superqt import QLabeledRangeSlider, QLabeledSlider
from superqt.iconify import QIconifyIcon
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from typing import Hashable, Mapping, TypeAlias

    from qtpy.QtGui import QMouseEvent

    DimensionKey: TypeAlias = Hashable
    Index: TypeAlias = int | slice
    Indices: TypeAlias = Mapping[DimensionKey, Index]


class PlayButton(QPushButton):
    """Just a styled QPushButton that toggles between play and pause icons."""

    PLAY_ICON = "fa6-solid:play"
    PAUSE_ICON = "fa6-solid:pause"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        icn = QIconifyIcon(self.PLAY_ICON)
        icn.addKey(self.PAUSE_ICON, state=QIconifyIcon.State.On)
        super().__init__(icn, text, parent)
        self.setCheckable(True)
        self.setMaximumWidth(22)


class LockButton(QPushButton):
    LOCK_ICON = "fa6-solid:lock-open"
    UNLOCK_ICON = "fa6-solid:lock"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        icn = QIconifyIcon(self.LOCK_ICON)
        icn.addKey(self.UNLOCK_ICON, state=QIconifyIcon.State.On)
        super().__init__(icn, text, parent)
        self.setCheckable(True)
        self.setMaximumWidth(20)


class DimsSlider(QWidget):
    """A single slider in the DimsSliders widget.

    Provides a play/pause button that toggles animation of the slider value.
    Has a QLabeledSlider for the actual value.
    Adds a label for the maximum value (e.g. "3 / 10")
    """

    valueChanged = Signal(str, object)  # where object is int | slice

    def __init__(
        self, dimension_key: DimensionKey, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._slice_mode = False
        self._animation_fps = 30
        self._dim_key = dimension_key

        self._play_btn = PlayButton()
        self._play_btn.toggled.connect(self._toggle_animation)

        self._dim_label = QLabel(str(dimension_key))

        # note, this lock button only prevents the slider from updating programmatically
        # using self.setValue, it doesn't prevent the user from changing the value.
        self._lock_btn = LockButton()

        self._max_label = QLabel("/ 0")
        self._int_slider = QLabeledSlider(Qt.Orientation.Horizontal, parent=self)
        self._int_slider.rangeChanged.connect(self._on_range_changed)
        self._int_slider.valueChanged.connect(self._on_int_value_changed)
        self._int_slider.layout().addWidget(self._max_label)

        self._slice_slider = QLabeledRangeSlider(Qt.Orientation.Horizontal, parent=self)
        self._slice_slider.setVisible(False)
        self._slice_slider.rangeChanged.connect(self._on_range_changed)
        self._slice_slider.valueChanged.connect(self._on_slice_value_changed)

        self.installEventFilter(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._play_btn)
        layout.addWidget(self._dim_label)
        layout.addWidget(self._int_slider)
        layout.addWidget(self._slice_slider)
        layout.addWidget(self._lock_btn)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self._set_slice_mode(not self._slice_mode)
        return super().mouseDoubleClickEvent(a0)

    def setMaximum(self, max_val: int) -> None:
        if max_val > self._int_slider.maximum():
            self._int_slider.setMaximum(max_val)
        if max_val > self._slice_slider.maximum():
            self._slice_slider.setMaximum(max_val)

    def setRange(self, min_val: int, max_val: int) -> None:
        self._int_slider.setRange(min_val, max_val)
        self._slice_slider.setRange(min_val, max_val)

    def value(self) -> Index:
        return (
            self._int_slider.value()
            if not self._slice_mode
            else slice(*self._slice_slider.value())
        )

    def setValue(self, val: Index) -> None:
        # variant of setValue that always updates the maximum
        self._set_slice_mode(isinstance(val, slice))
        if self._lock_btn.isChecked():
            return
        if isinstance(val, slice):
            self._slice_slider.setValue((val.start, val.stop))
            # self._int_slider.setValue(int((val.stop + val.start) / 2))
        else:
            self._int_slider.setValue(val)
            # self._slice_slider.setValue((val, val + 1))

    def forceValue(self, val: Index) -> None:
        """Set value and increase range if necessary."""
        self.setMaximum(val.stop if isinstance(val, slice) else val)
        self.setValue(val)

    def _set_slice_mode(self, mode: bool = True) -> None:
        self._slice_mode = mode
        if mode:
            self._slice_slider.setVisible(True)
            self._int_slider.setVisible(False)
        else:
            self._int_slider.setVisible(True)
            self._slice_slider.setVisible(False)

    def set_fps(self, fps: int) -> None:
        self._animation_fps = fps

    def _toggle_animation(self, checked: bool) -> None:
        if checked:
            self._timer_id = self.startTimer(1000 // self._animation_fps)
        else:
            self.killTimer(self._timer_id)

    def timerEvent(self, event: Any) -> None:
        if self._slice_mode:
            val = self._slice_slider.value()
            next_val = [v + 1 for v in val]
            if next_val[1] > self._slice_slider.maximum():
                next_val = [v - val[0] for v in val]
            self._slice_slider.setValue(next_val)
        else:
            val = self._int_slider.value()
            val = (val + 1) % (self._int_slider.maximum() + 1)
            self._int_slider.setValue(val)

    def _on_range_changed(self, min: int, max: int) -> None:
        self._max_label.setText("/ " + str(max))

    def _on_int_value_changed(self, value: int) -> None:
        if not self._slice_mode:
            self.valueChanged.emit(self._dim_key, value)

    def _on_slice_value_changed(self, value: tuple[int, int]) -> None:
        if self._slice_mode:
            self.valueChanged.emit(self._dim_key, slice(*value))


class DimsSliders(QWidget):
    """A Collection of DimsSlider widgets for each dimension in the data.

    Maintains the global current index and emits a signal when it changes.
    """

    valueChanged = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sliders: dict[DimensionKey, DimsSlider] = {}
        self._current_index: dict[DimensionKey, Index] = {}
        self._invisible_dims: set[DimensionKey] = set()
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def value(self) -> Indices:
        return self._current_index.copy()

    def setValue(self, values: Indices) -> None:
        if self._current_index == values:
            return
        with signals_blocked(self):
            for dim, index in values.items():
                self.add_or_update_dimension(dim, index)
        self.valueChanged.emit(self.value())

    def maximum(self) -> dict[DimensionKey, int]:
        return {k: v._int_slider.maximum() for k, v in self._sliders.items()}

    def add_dimension(self, name: DimensionKey, val: Index | None = None) -> None:
        self._sliders[name] = slider = DimsSlider(dimension_key=name, parent=self)
        slider.setRange(0, 1)
        val = val if val is not None else 0
        self._current_index[name] = val
        slider.forceValue(val)
        slider.valueChanged.connect(self._on_dim_slider_value_changed)
        slider.setVisible(name not in self._invisible_dims)
        self.layout().addWidget(slider)

    def set_dimension_visible(self, name: str, visible: bool) -> None:
        if visible:
            self._invisible_dims.discard(name)
        else:
            self._invisible_dims.add(name)
        if name in self._sliders:
            self._sliders[name].setVisible(visible)

    def remove_dimension(self, name: str) -> None:
        try:
            slider = self._sliders.pop(name)
        except KeyError:
            warn(f"Dimension {name} not found in DimsSliders", stacklevel=2)
            return
        self.layout().removeWidget(slider)
        slider.deleteLater()

    def _on_dim_slider_value_changed(self, dim_name: str, value: Index) -> None:
        self._current_index[dim_name] = value
        if not self._updating:
            self.valueChanged.emit(self.value())

    def add_or_update_dimension(self, name: DimensionKey, value: Index) -> None:
        if name in self._sliders:
            self._sliders[name].forceValue(value)
        else:
            self.add_dimension(name, value)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    w = DimsSliders()
    w.add_dimension("x")
    w.add_dimension("y", slice(5, 9))
    w.add_dimension("z", 10)
    w.valueChanged.connect(print)
    w.show()
    app.exec()
