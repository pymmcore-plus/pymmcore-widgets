from __future__ import annotations

from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

FIXED_POLICY = (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


def create_label(label_text: str) -> QLabel:
    """Create a QLabel with fixed QSizePolicy."""
    lbl = QLabel()
    lbl.setSizePolicy(*FIXED_POLICY)
    lbl.setText(label_text)
    return lbl


def make_wdg_with_label(label: QLabel, wdg: QWidget) -> QWidget:
    """Create a QWidget with a QHBoxLayout with the given label and widget."""
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    layout.addWidget(label)
    layout.addWidget(wdg)
    return widget
