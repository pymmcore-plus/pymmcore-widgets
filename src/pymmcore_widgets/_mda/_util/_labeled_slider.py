from __future__ import annotations

from typing import Any, cast

import superqt
from fonticon_mdi6 import MDI6
from qtpy import QtCore, QtWidgets
from superqt.fonticon import icon

FIXED = QtWidgets.QSizePolicy.Policy.Fixed


class QLabeledSlider(superqt.QLabeledSlider):
    def __init__(
        self,
        name: str = "",
        orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Horizontal,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self.name = name
        name_label = QtWidgets.QLabel(name.upper())

        self._length_label = QtWidgets.QLabel()
        self.rangeChanged.connect(self._on_range_changed)

        self.play_btn = QtWidgets.QPushButton(icon(MDI6.play), "", self)
        self.play_btn.setMaximumWidth(24)
        self.play_btn.setCheckable(True)
        self.play_btn.toggled.connect(self._on_play_toggled)

        layout = cast(QtWidgets.QBoxLayout, self.layout())
        layout.insertWidget(0, self.play_btn, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        layout.insertWidget(0, name_label)
        # FIXME: the padding/vertical alignment is a bit off here
        layout.addWidget(self._length_label, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

    def _on_play_toggled(self, state: bool) -> None:
        if state:
            self.play_btn.setIcon(icon(MDI6.pause))
            self._timer_id = self.startTimer(50)
        else:
            self.play_btn.setIcon(icon(MDI6.play))
            self.killTimer(self._timer_id)

    def timerEvent(self, e: QtCore.QTimerEvent) -> None:
        self.setValue((self.value() + 1) % self.maximum())

    def _on_range_changed(self, min_: int, max_: int) -> None:
        self._length_label.setText(f"/ {max_}")


class LabeledVisibilitySlider(QLabeledSlider):
    def _visibility(self, settings: dict[str, Any]) -> None:
        if settings["index"] != self.name:
            return
        if settings["show"]:
            self.show()
        else:
            self.hide()
        self.setRange(0, settings["max"])
