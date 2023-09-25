from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus


class _AutofocusZDeviceWidget(QWidget):
    """Widget to select the hardware autofocus z device."""

    toggled = Signal(object)

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self.af_checkbox = QCheckBox("Use Autofocus:")
        self.af_checkbox.setChecked(True)
        self.af_checkbox.toggled.connect(self._on_checkbox_toggled)

        self.af_combo = QComboBox()
        self.af_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._selector_wdg = QWidget()
        self._selector_wdg.setLayout(QHBoxLayout())
        self._selector_wdg.layout().setSpacing(5)
        self._selector_wdg.layout().setContentsMargins(0, 0, 0, 0)
        self._selector_wdg.layout().addWidget(self.af_combo)

        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(10)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.af_checkbox)
        self.layout().addWidget(self._selector_wdg)

        self.setMinimumWidth(self.sizeHint().width())
        self.setMinimumHeight(self.minimumSizeHint().height())

    def _on_checkbox_toggled(self, checked: bool) -> None:
        self._selector_wdg.show() if checked else self._selector_wdg.hide()
        self.toggled.emit(checked)

    def value(self) -> str | None:
        """Return the current autofocus z device."""
        _af_z_device = self.af_combo.currentText()
        return _af_z_device if self.af_checkbox.isChecked() and _af_z_device else None

    def setValue(self, value: str) -> None:
        """Set the autofocus device to use."""
        if not isinstance(value, str):  # pragma: no cover
            raise TypeError(f"Expected 'str', got {type(value)}")

        items = [self.af_combo.itemText(i) for i in range(self.af_combo.count())]

        if value in items:
            self.af_combo.setCurrentText(value)
            self.af_checkbox.setChecked(True)
        else:
            self.af_checkbox.setChecked(False)
            warnings.warn(
                f"Autofocus device '{value}' not found in device list: {items}",
                stacklevel=2,
            )
