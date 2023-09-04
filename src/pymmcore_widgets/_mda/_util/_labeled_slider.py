from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

FIXED = QtWidgets.QSizePolicy.Policy.Fixed


class QLabeledSlider(QtWidgets.QWidget):
    """Slider that shows name of the axis and current value."""

    valueChanged = QtCore.Signal([int], [int, str])
    sliderPressed = QtCore.Signal()
    sliderMoved = QtCore.Signal()
    sliderReleased = QtCore.Signal()

    def __init__(
        self,
        name: str = "",
        orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Horizontal,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.name = name

        self.label = QtWidgets.QLabel()
        self.label.setText(name.upper())
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.label.setSizePolicy(FIXED, FIXED)
        self.slider = QtWidgets.QSlider(orientation)
        for function in [
            "blockSignals",
            "setTickInterval",
            "setTickPosition",
            "tickInterval",
            "tickPosition",
            "setTracking",
        ]:
            func = getattr(self.slider, function)
            setattr(self, function, func)

        self.current_value = QtWidgets.QLabel()
        self.current_value.setText("0")
        self.current_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.current_value.setSizePolicy(FIXED, FIXED)

        self.play_btn = QtWidgets.QPushButton("▶")
        self.play_btn.setStyleSheet("QPushButton {padding: 2px;}")
        self.play_btn.setFont(QtGui.QFont("Times", 14))
        self.play_btn.clicked.connect(self.play_clk)

        # self.layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.label)
        self.layout().addWidget(self.play_btn)
        self.layout().addWidget(self.slider)
        self.layout().addWidget(self.current_value)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, FIXED)

        self.slider.valueChanged.connect(self.on_drag_timer)
        self.slider.sliderPressed.connect(self.sliderPressed)
        self.slider.sliderMoved.connect(self.sliderMoved)
        self.slider.sliderReleased.connect(self.sliderReleased)
        self.playing = False

        self.play_timer = QtCore.QTimer()
        self.play_timer.setInterval(10)
        self.play_timer.timeout.connect(self.on_play_timer)

        self.drag_timer = QtCore.QTimer()
        self.drag_timer.setInterval(10)
        self.drag_timer.timeout.connect(self.on_drag_timer)

    def _start_play_timer(self, playing: bool) -> None:
        if playing:
            self.play_timer.start(10)
        else:
            self.play_timer.stop()

    def on_play_timer(self) -> None:
        value = self.value() + 1
        value = value % self.maximum()
        self.setValue(value)

    def setMaximum(self, maximum: int) -> None:
        self.current_value.setText(f"{self.value()!s}/{maximum!s}")
        self.slider.setMaximum(maximum)

    def setRange(self, minimum: int, maximum: int) -> None:
        self.current_value.setText(f"{self.value()!s}/{maximum!s}")
        self.slider.setMaximum(maximum)

    def setValue(self, value: int) -> None:
        self.current_value.setText(f"{value!s}/{self.maximum()!s}")
        self.slider.setValue(value)

    def play_clk(self) -> None:
        if self.playing:
            self.play_btn.setText("▶")
            self.play_timer.stop()
        else:
            self.play_btn.setText("■")
            self.play_timer.start()
        self.playing = not self.playing

    def on_slider_press(self) -> None:
        self.slider.valueChanged.disconnect(self.on_drag_timer)
        self.drag_timer.start()

    def on_slider_release(self) -> None:
        self.drag_timer.stop()
        self.slider.valueChanged.connect(self.on_drag_timer)

    def on_drag_timer(self) -> None:
        self.valueChanged[int, str].emit(self.value(), self.name)

    def value(self) -> int:
        return self.slider.value()  # type: ignore

    def maximum(self) -> int:
        return self.slider.maximum()  # type: ignore

    def minimum(self) -> int:
        return self.slider.minimum()  # type: ignore


class LabeledVisibilitySlider(QLabeledSlider):
    def _visibility(self, settings: dict[str, Any]) -> None:
        if settings["index"] != self.name:
            return
        if settings["show"]:
            self.show()
        else:
            self.hide()
        self.setRange(0, settings["max"])
