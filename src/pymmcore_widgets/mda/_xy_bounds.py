from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QTransform
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from superqt.fonticon import icon

if TYPE_CHECKING:
    from pymmcore import CMMCore


FIXED_POLICY = (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
CTR = Qt.AlignmentFlag.AlignCenter
RADIUS = 4
ICON_SIZE = TRANSLATE_ICON = 24
if os.name != "nt":
    TRANSLATE_ICON *= 2


# we have zero idea why this works. But we found that the classic
# translate -> rotate -> inverse-translate does not work on Windows
# We don't know why this would be OS dependent in the first place
def _rotate(deg: int, size_x: int, size_y: int) -> QTransform:
    return QTransform().translate(size_x, size_y).rotate(deg)


ICONS_GO: dict[str, str] = {
    "top": MDI6.arrow_up_thick,
    "left": MDI6.arrow_left_thick,
    "right": MDI6.arrow_right_thick,
    "bottom": MDI6.arrow_down_thick,
    "top_left": MDI6.arrow_top_left_thick,
    "top_right": MDI6.arrow_top_right_thick,
    "bottom_left": MDI6.arrow_bottom_left_thick,
    "bottom_right": MDI6.arrow_bottom_right_thick,
}
ICONS_MARK: dict[str, tuple[str, QTransform | None]] = {
    "top": (MDI6.border_top_variant, None),
    "left": (MDI6.border_left_variant, None),
    "right": (MDI6.border_right_variant, None),
    "bottom": (MDI6.border_bottom_variant, None),
    "top_left": (MDI6.border_style, None),
    "top_right": (MDI6.border_style, _rotate(90, TRANSLATE_ICON, 0)),
    "bottom_left": (MDI6.border_style, _rotate(270, 0, TRANSLATE_ICON)),
    "bottom_right": (MDI6.border_style, _rotate(180, TRANSLATE_ICON, TRANSLATE_ICON)),
}

BTN_STYLE = f"""
QPushButton {{
    border-radius: {RADIUS}px;
    border: 0.5px solid #DCDCDC;
    background-color: #FFF;
    padding: 2px 6px;
}}
QPushButton:hover {{
    background-color: #EEE;
}}
QPushButton:pressed {{
    background-color: #AAA;
}}
"""
# styles for paired buttons
SS = """
QPushButton {{
    border-top-{side}-radius: {radius}px;
    border-bottom-{side}-radius: {radius}px;
    border: 1px solid #A3A3A3;
    padding: 2px 6px;
}}
QPushButton:hover {{
    background-color: #ABABAB;
}}
QPushButton:pressed {{
    background-color: #8C8C8C;
}}
"""


class XYBoundsControl(QWidget):
    """Buttons to mark and visit bounds on the XY stage."""

    def __init__(
        self, compact_layout: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self.top_edit = _PositionSpinBox()
        self.left_edit = _PositionSpinBox()
        self.right_edit = _PositionSpinBox()
        self.bottom_edit = _PositionSpinBox()

        self.btn_top = _MarkVisitButton("top")
        self.btn_left = _MarkVisitButton("left")
        self.btn_right = _MarkVisitButton("right")
        self.btn_bottom = _MarkVisitButton("bottom")
        self.btn_top_left = _MarkVisitButton("top_left")
        self.btn_top_right = _MarkVisitButton("top_right")
        self.btn_bottom_left = _MarkVisitButton("bottom_left")
        self.btn_bottom_right = _MarkVisitButton("bottom_right")

        self.go_middle = QCheckBox("Move")
        self.go_middle.setSizePolicy(*FIXED_POLICY)
        self.go_middle.toggled.connect(self._update_buttons_icon)

        grid = QWidget()
        grid.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        grid_layout = QGridLayout(grid)
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.btn_top, 0, 2, CTR)
        grid_layout.addWidget(self.btn_left, 1 if compact_layout else 2, 0, CTR)
        grid_layout.addWidget(self.btn_right, 1 if compact_layout else 2, 4, CTR)
        grid_layout.addWidget(self.btn_bottom, 4, 2, CTR)

        grid_layout.addWidget(self.btn_top_left, 0, 0, CTR)
        grid_layout.addWidget(self.btn_top_right, 0, 4, CTR)
        grid_layout.addWidget(self.btn_bottom_left, 4, 0, CTR)
        grid_layout.addWidget(self.btn_bottom_right, 4, 4, CTR)

        grid_layout.addWidget(self.go_middle, 2, 2, CTR)

        values_layout = QFormLayout()
        values_layout.setContentsMargins(0, 0, 0, 0)
        values_layout.setSpacing(10)
        values_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        values_layout.addRow("Top:", self.top_edit)
        values_layout.addRow("Left:", self.left_edit)
        values_layout.addRow("Right:", self.right_edit)
        values_layout.addRow("Bottom:", self.bottom_edit)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(15)
        top_layout.addWidget(grid)
        top_layout.addLayout(values_layout)

        self.setLayout(top_layout)
        self.setWindowTitle("Mark XY Boundaries")
        self.show()

    def _update_buttons_icon(self, state: bool) -> None:
        """Switch the icon of the buttons between `mark` and `visit`."""
        for btn in self.findChildren(_MarkVisitButton):
            btn.setVisit() if state else btn.setMark()


class CoreXYBoundsControl(XYBoundsControl):
    """Buttons to mark and visit bounds on the XY stage from a CMMCorePlus instance."""

    def __init__(
        self,
        core: CMMCore | None = None,
        device: str = "",
        compact_layout: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(compact_layout, parent)
        self._mmc = core or CMMCorePlus.instance()
        self._device = device

        self.btn_top.clicked.connect(lambda: self._mark_or_visit(top=True))
        self.btn_left.clicked.connect(lambda: self._mark_or_visit(left=True))
        self.btn_right.clicked.connect(lambda: self._mark_or_visit(left=False))
        self.btn_bottom.clicked.connect(lambda: self._mark_or_visit(top=False))
        self.btn_top_left.clicked.connect(lambda: self._mark_or_visit(True, True))
        self.btn_top_right.clicked.connect(lambda: self._mark_or_visit(True, False))
        self.btn_bottom_left.clicked.connect(lambda: self._mark_or_visit(False, True))
        self.btn_bottom_right.clicked.connect(lambda: self._mark_or_visit(False, False))

    def _mark_or_visit(self, top: bool | None = None, left: bool | None = None) -> None:
        self._visit(top, left) if self.go_middle.isChecked() else self._mark(top, left)

    def _mark(self, top: bool | None = None, left: bool | None = None) -> None:
        device = self._device or self._mmc.getXYStageDevice()
        if top is not None:
            wdg = self.top_edit if top else self.bottom_edit
            wdg.setValue(self._mmc.getYPosition(device))
        if left is not None:
            wdg = self.left_edit if left else self.right_edit
            wdg.setValue(self._mmc.getXPosition(device))

    def _visit(self, top: bool | None = None, left: bool | None = None) -> None:
        device = self._device or self._mmc.getXYStageDevice()
        if top is None:
            y = self._mmc.getYPosition(device)
        else:
            y = self.top_edit.value() if top else self.bottom_edit.value()
        if left is None:
            x = self._mmc.getXPosition(device)
        else:
            x = self.left_edit.value() if left else self.right_edit.value()

        self._mmc.setXYPosition(device, x, y)
        self._mmc.waitForDevice(device)


# -------- helpers --------


class _PositionSpinBox(QDoubleSpinBox):
    def __init__(self) -> None:
        super().__init__()
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setRange(-99999999, 99999999)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSuffix(" µm")


class _MarkVisitButton(QPushButton):
    def __init__(
        self,
        name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._visit_icon = icon(ICONS_GO[self._name])
        glyph, transform = ICONS_MARK[self._name]
        self._mark_icon = icon(glyph, transform=transform)

        self.setIcon(self._mark_icon)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(BTN_STYLE)
        self.setToolTip(f"Mark the {self._name} bound.")

    def setMark(self) -> None:
        """Set the icon to the mark icon."""
        self.setIcon(self._mark_icon)
        self.setToolTip(f"Mark the {self._name} bound.")

    def setVisit(self) -> None:
        """Set the icon to the visit icon."""
        self.setIcon(self._visit_icon)
        self.setToolTip(f"Move to the {self._name} bound.")


class MarkVisit(QWidget):
    def __init__(
        self,
        mark_glyph: str,
        mark_text: str = "",
        icon_size: int = ICON_SIZE,
        radius: int = RADIUS,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        mode = "top" if "top" in mark_text.lower() else "bottom"

        self.mark = QPushButton(icon(mark_glyph), mark_text)
        self.mark.setIconSize(QSize(icon_size, icon_size))
        self.mark.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.visit = QPushButton(icon(ICONS_GO[mode]), "")
        self.visit.setIconSize(QSize(icon_size, icon_size))
        self.visit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.visit.setToolTip(f"Move to {mode}.")

        left_style = SS.format(side="left", radius=radius)
        right_style = SS.format(side="right", radius=radius)

        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mark.setStyleSheet(left_style)
        self.visit.setStyleSheet(right_style)
        layout.addWidget(self.mark)
        layout.addWidget(self.visit)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    core = CMMCorePlus.instance()
    core.loadSystemConfiguration()
    wdg = CoreXYBoundsControl(core)

    wdg.show()
    sys.exit(app.exec())
