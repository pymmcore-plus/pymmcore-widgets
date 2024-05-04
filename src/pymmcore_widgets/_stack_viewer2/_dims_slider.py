from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from warnings import warn

from qtpy.QtCore import QPointF, QSize, Qt, Signal
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QElidingLabel, QLabeledRangeSlider
from superqt.iconify import QIconifyIcon
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from typing import Hashable, Mapping, TypeAlias

    from PyQt6.QtGui import QResizeEvent
    from qtpy.QtGui import QKeyEvent

    # any hashable represent a single dimension in a AND array
    DimensionKey: TypeAlias = Hashable
    # any object that can be used to index a single dimension in an AND array
    Index: TypeAlias = int | slice
    # a mapping from dimension keys to indices (eg. {"x": 0, "y": slice(5, 10)})
    # this object is used frequently to query or set the currently displayed slice
    Indices: TypeAlias = Mapping[DimensionKey, Index]
    # mapping of dimension keys to the maximum value for that dimension
    Sizes: TypeAlias = Mapping[DimensionKey, int]


SS = """
QSlider::groove:horizontal {
    height: 6px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(128, 128, 128, 0.25),
        stop:1 rgba(128, 128, 128, 0.1)
    );
    border-radius: 3px;
    margin: 2px 0;
}

QSlider::handle:horizontal {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(180, 180, 180, 1),
        stop:1 rgba(180, 180, 180, 1)
    );
    width: 28px;
    margin: -3px 0;
    border-radius: 3px;
}"""


class _DissmissableDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup
        )

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e and e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape):
            self.accept()
            print("accept")


class PlayButton(QPushButton):
    """Just a styled QPushButton that toggles between play and pause icons."""

    fpsChanged = Signal(int)

    PLAY_ICON = "bi:play-fill"
    PAUSE_ICON = "bi:pause-fill"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        icn = QIconifyIcon(self.PLAY_ICON)
        icn.addKey(self.PAUSE_ICON, state=QIconifyIcon.State.On)
        super().__init__(icn, text, parent)
        self.setCheckable(True)
        self.setFixedSize(14, 18)
        self.setIconSize(QSize(16, 16))
        self.setStyleSheet("border: none; padding: 0; margin: 0;")

    # def mousePressEvent(self, e: QMouseEvent | None) -> None:
    #     if e and e.button() == Qt.MouseButton.RightButton:
    #         self._show_fps_dialog(e.globalPosition())
    #     else:
    #         super().mousePressEvent(e)

    def _show_fps_dialog(self, pos: QPointF) -> None:
        dialog = _DissmissableDialog()

        sb = QSpinBox()
        sb.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        sb.valueChanged.connect(self.fpsChanged)

        layout = QHBoxLayout(dialog)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(QLabel("FPS"))
        layout.addWidget(sb)

        dialog.setGeometry(int(pos.x()) - 20, int(pos.y()) - 50, 40, 40)
        dialog.exec()


class LockButton(QPushButton):
    LOCK_ICON = "uis:unlock"
    UNLOCK_ICON = "uis:lock"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        icn = QIconifyIcon(self.LOCK_ICON)
        icn.addKey(self.UNLOCK_ICON, state=QIconifyIcon.State.On)
        super().__init__(icn, text, parent)
        self.setCheckable(True)
        self.setFixedSize(20, 20)
        self.setIconSize(QSize(14, 14))
        self.setStyleSheet("border: none; padding: 0; margin: 0;")


class DimsSlider(QWidget):
    """A single slider in the DimsSliders widget.

    Provides a play/pause button that toggles animation of the slider value.
    Has a QLabeledSlider for the actual value.
    Adds a label for the maximum value (e.g. "3 / 10")
    """

    valueChanged = Signal(object, object)  # where object is int | slice

    def __init__(
        self, dimension_key: DimensionKey, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(SS)
        self._slice_mode = False
        self._animation_fps = 30
        self._dim_key = dimension_key

        self._play_btn = PlayButton()
        self._play_btn.fpsChanged.connect(self.set_fps)
        self._play_btn.toggled.connect(self._toggle_animation)

        self._dim_label = QElidingLabel(str(dimension_key).upper())

        # note, this lock button only prevents the slider from updating programmatically
        # using self.setValue, it doesn't prevent the user from changing the value.
        self._lock_btn = LockButton()

        self._pos_label = QSpinBox()
        self._pos_label.valueChanged.connect(self._on_pos_label_edited)
        self._pos_label.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._pos_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._pos_label.setStyleSheet(
            "border: none; padding: 0; margin: 0; background: transparent"
        )

        self._int_slider = QSlider(Qt.Orientation.Horizontal, parent=self)
        self._int_slider.rangeChanged.connect(self._on_range_changed)
        self._int_slider.valueChanged.connect(self._on_int_value_changed)
        # self._int_slider.layout().addWidget(self._max_label)

        self._slice_slider = QLabeledRangeSlider(Qt.Orientation.Horizontal, parent=self)
        self._slice_slider.setVisible(False)
        # self._slice_slider.rangeChanged.connect(self._on_range_changed)
        # self._slice_slider.valueChanged.connect(self._on_slice_value_changed)

        self.installEventFilter(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._play_btn)
        layout.addWidget(self._dim_label)
        layout.addWidget(self._int_slider)
        layout.addWidget(self._pos_label)
        layout.addWidget(self._lock_btn)
        self.setMinimumHeight(22)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        # align all labels
        if isinstance(par := self.parent(), DimsSliders):
            lbl_width = max(
                x._dim_label.sizeHint().width() for x in par.findChildren(DimsSlider)
            )
            self._dim_label.setFixedWidth(min(lbl_width + 2, 40))
            pos_lbl_width = max(
                x._pos_label.sizeHint().width() for x in par.findChildren(DimsSlider)
            )
            self._pos_label.setFixedWidth(min(pos_lbl_width + 2, 40))
        return super().resizeEvent(a0)

    # def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
    #     self._set_slice_mode(not self._slice_mode)
    #     return super().mouseDoubleClickEvent(a0)

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
            val = cast(tuple[int, int], self._slice_slider.value())
            next_val = [v + 1 for v in val]
            if next_val[1] > self._slice_slider.maximum():
                next_val = [v - val[0] for v in val]
            self._slice_slider.setValue(next_val)
        else:
            ival = self._int_slider.value()
            ival = (ival + 1) % (self._int_slider.maximum() + 1)
            self._int_slider.setValue(ival)

    def _on_pos_label_edited(self) -> None:
        if self._slice_mode:
            self._slice_slider.setValue(
                (self._pos_label.value(), self._pos_label.value() + 1)
            )
        else:
            self._int_slider.setValue(self._pos_label.value())

    def _on_range_changed(self, min: int, max: int) -> None:
        self._pos_label.setSuffix(" / " + str(max))
        self._pos_label.setRange(min, max)

    def _on_int_value_changed(self, value: int) -> None:
        self._pos_label.setValue(value)
        if not self._slice_mode:
            self.valueChanged.emit(self._dim_key, value)

    def _on_slice_value_changed(self, value: tuple[int, int]) -> None:
        if self._slice_mode:
            self.valueChanged.emit(self._dim_key, slice(*value))


class DimsSliders(QWidget):
    """A Collection of DimsSlider widgets for each dimension in the data.

    Maintains the global current index and emits a signal when it changes.
    """

    valueChanged = Signal(dict)  # dict is of type Indices

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sliders: dict[DimensionKey, DimsSlider] = {}
        self._current_index: dict[DimensionKey, Index] = {}
        self._invisible_dims: set[DimensionKey] = set()

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)

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

    def maximum(self) -> Sizes:
        return {k: v._int_slider.maximum() for k, v in self._sliders.items()}

    def setMaximum(self, values: Sizes) -> None:
        for name, max_val in values.items():
            if name not in self._sliders:
                self.add_dimension(name)
            self._sliders[name].setMaximum(max_val)

    def add_dimension(self, name: DimensionKey, val: Index | None = None) -> None:
        self._sliders[name] = slider = DimsSlider(dimension_key=name, parent=self)
        slider.setRange(0, 1)
        val = val if val is not None else 0
        self._current_index[name] = val
        slider.forceValue(val)
        slider.valueChanged.connect(self._on_dim_slider_value_changed)
        slider.setVisible(name not in self._invisible_dims)
        cast("QVBoxLayout", self.layout()).addWidget(slider)

    def set_dimension_visible(self, key: DimensionKey, visible: bool) -> None:
        if visible:
            self._invisible_dims.discard(key)
        else:
            self._invisible_dims.add(key)
        if key in self._sliders:
            self._sliders[key].setVisible(visible)

    def remove_dimension(self, key: DimensionKey) -> None:
        try:
            slider = self._sliders.pop(key)
        except KeyError:
            warn(f"Dimension {key} not found in DimsSliders", stacklevel=2)
            return
        cast("QVBoxLayout", self.layout()).removeWidget(slider)
        slider.deleteLater()

    def _on_dim_slider_value_changed(self, key: DimensionKey, value: Index) -> None:
        self._current_index[key] = value
        self.valueChanged.emit(self.value())

    def add_or_update_dimension(self, key: DimensionKey, value: Index) -> None:
        if key in self._sliders:
            self._sliders[key].forceValue(value)
        else:
            self.add_dimension(key, value)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    w = DimsSliders()
    w.add_dimension("x", 5)
    w.add_dimension("ysadfdasas", 20)
    w.add_dimension("z", 10)
    w.add_dimension("w", 10)
    w.valueChanged.connect(print)
    w.show()
    app.exec()
