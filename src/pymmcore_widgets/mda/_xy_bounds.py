from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
)
from superqt.fonticon import icon

if TYPE_CHECKING:
    from pymmcore import CMMCore

RADIUS = 4
ICON_SIZE = 24
ICONS: dict[str, str] = {
    "top": MDI6.arrow_collapse_up,  # or arrow_up
    "left": MDI6.arrow_collapse_left,  # or arrow_left
    "right": MDI6.arrow_collapse_right,  # or arrow_right
    "bottom": MDI6.arrow_collapse_down,  # or arrow_down
    "top_left": MDI6.arrow_top_left,
    "top_right": MDI6.arrow_top_right,
    "bottom_left": MDI6.arrow_bottom_left,
    "bottom_right": MDI6.arrow_bottom_right,
    "visit": MDI6.language_go,
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
    border: 0.5px solid #DCDCDC;
    background-color: #FFF;
    padding: 2px 6px;
    {extra}
}}
QPushButton:hover {{
    background-color: #EEE;
}}
QPushButton:pressed {{
    background-color: #AAA;
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

        self.btn_top = MarkVisit(ICONS["top"])
        self.btn_left = MarkVisit(ICONS["left"], visit_on_right=False)
        self.btn_right = MarkVisit(ICONS["right"])
        self.btn_bottom = MarkVisit(ICONS["bottom"])
        self.btn_top_left = MarkVisit(ICONS["top_left"], visit_on_right=False)
        self.btn_top_right = MarkVisit(ICONS["top_right"])
        self.btn_bottom_left = MarkVisit(ICONS["bottom_left"], visit_on_right=False)
        self.btn_bottom_right = MarkVisit(ICONS["bottom_right"])

        self.go_middle = QPushButton(icon(ICONS["visit"]), "")
        self.go_middle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.go_middle.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.go_middle.setStyleSheet(BTN_STYLE)

        grid_layout = QGridLayout()
        CTR = Qt.AlignmentFlag.AlignCenter
        grid_layout.addWidget(self.top_edit, 1, 2, CTR)
        grid_layout.addWidget(self.left_edit, 2, 0 if compact_layout else 1, CTR)
        grid_layout.addWidget(self.right_edit, 2, 4 if compact_layout else 3, CTR)
        grid_layout.addWidget(self.bottom_edit, 3, 2, CTR)
        grid_layout.addWidget(self.btn_top, 0, 2, CTR)
        grid_layout.addWidget(self.btn_left, 1 if compact_layout else 2, 0, CTR)
        grid_layout.addWidget(self.btn_right, 1 if compact_layout else 2, 4, CTR)
        grid_layout.addWidget(self.btn_bottom, 4, 2, CTR)

        grid_layout.addWidget(self.btn_top_left, 0, 0, CTR)
        grid_layout.addWidget(self.btn_top_right, 0, 4, CTR)
        grid_layout.addWidget(self.btn_bottom_left, 4, 0, CTR)
        grid_layout.addWidget(self.btn_bottom_right, 4, 4, CTR)
        grid_layout.addWidget(self.go_middle, 2, 2, CTR)

        self.setLayout(grid_layout)
        self.setWindowTitle("XY Stage Control")
        self.show()


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

        self.btn_top.mark.clicked.connect(lambda: self._mark(top=True))
        self.btn_left.mark.clicked.connect(lambda: self._mark(left=True))
        self.btn_right.mark.clicked.connect(lambda: self._mark(left=False))
        self.btn_bottom.mark.clicked.connect(lambda: self._mark(top=False))
        self.btn_top_left.mark.clicked.connect(lambda: self._mark(True, True))
        self.btn_top_right.mark.clicked.connect(lambda: self._mark(True, False))
        self.btn_bottom_left.mark.clicked.connect(lambda: self._mark(False, True))
        self.btn_bottom_right.mark.clicked.connect(lambda: self._mark(False, False))

        self.btn_top.visit.clicked.connect(lambda: self._visit(top=True))
        self.btn_left.visit.clicked.connect(lambda: self._visit(left=True))
        self.btn_right.visit.clicked.connect(lambda: self._visit(left=False))
        self.btn_bottom.visit.clicked.connect(lambda: self._visit(top=False))
        self.btn_top_left.visit.clicked.connect(lambda: self._visit(True, True))
        self.btn_top_right.visit.clicked.connect(lambda: self._visit(True, False))
        self.btn_bottom_left.visit.clicked.connect(lambda: self._visit(False, True))
        self.btn_bottom_right.visit.clicked.connect(lambda: self._visit(False, False))

        self.go_middle.clicked.connect(self._visit_middle)

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

    def _visit_middle(self) -> None:
        device = self._device or self._mmc.getXYStageDevice()
        x = (self.left_edit.value() + self.right_edit.value()) / 2
        y = (self.top_edit.value() + self.bottom_edit.value()) / 2
        self._mmc.setXYPosition(device, x, y)
        self._mmc.waitForDevice(device)


# -------- helpers --------
class _PositionSpinBox(QDoubleSpinBox):
    def __init__(self) -> None:
        super().__init__()
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setRange(-99999999, 99999999)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class MarkVisit(QWidget):
    def __init__(
        self,
        mark_glyph: str,
        visit_glyph: str = ICONS["visit"],
        mark_text: str = "",
        icon_size: int = ICON_SIZE,
        radius: int = RADIUS,
        visit_on_right: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.mark = QPushButton(icon(mark_glyph), mark_text)
        self.mark.setIconSize(QSize(icon_size, icon_size))
        self.mark.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.visit = QPushButton(icon(visit_glyph), "")
        self.visit.setIconSize(QSize(icon_size, icon_size))
        self.visit.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        left_style = SS.format(side="left", radius=radius, extra="border-right: none;")
        right_style = SS.format(side="right", radius=radius, extra="")

        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        if visit_on_right:
            self.mark.setStyleSheet(left_style)
            self.visit.setStyleSheet(right_style)
            layout.addWidget(self.mark)
            layout.addWidget(self.visit)
        else:
            self.mark.setStyleSheet(right_style)
            self.visit.setStyleSheet(left_style)
            layout.addWidget(self.visit)
            layout.addWidget(self.mark)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    core = CMMCorePlus.instance()
    core.loadSystemConfiguration()
    wdg = CoreXYBoundsControl(core)

    wdg.show()
    sys.exit(app.exec())
