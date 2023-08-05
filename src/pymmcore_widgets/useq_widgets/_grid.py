from enum import Enum
from typing import TYPE_CHECKING, cast

import useq
from qtpy.QtCore import QPoint, QSize, Qt
from qtpy.QtGui import QPainter, QPaintEvent, QPen
from qtpy.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QEnumComboBox

if TYPE_CHECKING:
    from git import Sequence


class RelativeTo(Enum):
    center = "center"
    top_left = "top_left"


class OrderMode(Enum):
    """Different ways of ordering the grid positions."""

    row_wise = "row_wise"
    column_wise = "column_wise"
    row_wise_snake = "row_wise_snake"
    column_wise_snake = "column_wise_snake"
    spiral = "spiral"


class Mode(Enum):
    NUMBER = "number"
    AREA = "area"
    BOUNDS = "bounds"


class ImageGrid(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.rows = QSpinBox()
        self.rows.setRange(1, 1000)
        self.rows.setValue(1)
        self.rows.setSuffix(" fields")
        self.columns = QSpinBox()
        self.columns.setRange(1, 1000)
        self.columns.setValue(1)
        self.columns.setSuffix(" fields")

        self.area_width = QDoubleSpinBox()
        self.area_width.setRange(0, 100)
        self.area_width.setValue(0)
        self.area_width.setDecimals(2)
        self.area_width.setSuffix(" mm")
        self.area_width.setSingleStep(0.1)
        self.area_height = QDoubleSpinBox()
        self.area_height.setRange(0, 100)
        self.area_height.setValue(0)
        self.area_height.setDecimals(2)
        self.area_height.setSuffix(" mm")
        self.area_height.setSingleStep(0.1)

        self.left = QDoubleSpinBox()
        self.left.setRange(-10000, 10000)
        self.left.setValue(0)
        self.left.setDecimals(3)
        self.left.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.top = QDoubleSpinBox()
        self.top.setRange(-10000, 10000)
        self.top.setValue(0)
        self.top.setDecimals(3)
        self.top.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.right = QDoubleSpinBox()
        self.right.setRange(-10000, 10000)
        self.right.setValue(0)
        self.right.setDecimals(3)
        self.right.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.bottom = QDoubleSpinBox()
        self.bottom.setRange(-10000, 10000)
        self.bottom.setValue(0)
        self.bottom.setDecimals(3)
        self.bottom.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)

        self.overlap = QSpinBox()
        self.overlap.setRange(-1000, 1000)
        self.overlap.setValue(0)
        self.overlap.setSuffix(" %")

        self.order = QEnumComboBox(self, OrderMode)
        self.relative_to = QEnumComboBox(self, RelativeTo)
        self.order.currentEnum()

        self._mode_number_radio = QRadioButton()
        self._mode_area_radio = QRadioButton()
        self._mode_bounds_radio = QRadioButton()
        self._mode_btn_group = QButtonGroup()
        self._mode_btn_group.addButton(self._mode_number_radio)
        self._mode_btn_group.addButton(self._mode_area_radio)
        self._mode_btn_group.addButton(self._mode_bounds_radio)
        self._mode_btn_group.buttonToggled.connect(self.setMode)

        row_1 = QHBoxLayout()
        row_1.addWidget(self._mode_number_radio)
        row_1.addWidget(QLabel("Rows:"))
        row_1.addWidget(self.rows)
        row_1.addWidget(QLabel("x Cols:"))
        row_1.addWidget(self.columns)

        row_2 = QHBoxLayout()
        row_2.addWidget(self._mode_area_radio)
        row_2.addWidget(QLabel("Width:"))
        row_2.addWidget(self.area_width)
        row_2.addWidget(QLabel("x Height:"))
        row_2.addWidget(self.area_height)

        lrtb_grid = QGridLayout()
        lrtb_grid.addWidget(QLabel("Left:"), 0, 0)
        lrtb_grid.addWidget(self.left, 0, 1)
        lrtb_grid.addWidget(QLabel("Top:"), 0, 2)
        lrtb_grid.addWidget(self.top, 0, 3)
        lrtb_grid.addWidget(QLabel("Right:"), 1, 0)
        lrtb_grid.addWidget(self.right, 1, 1)
        lrtb_grid.addWidget(QLabel("Bottom:"), 1, 2)
        lrtb_grid.addWidget(self.bottom, 1, 3)

        row_3 = QHBoxLayout()
        row_3.addWidget(self._mode_bounds_radio)
        row_3.addLayout(lrtb_grid)

        row_4 = QHBoxLayout()
        row_4.addWidget(QLabel("Overlap:"))
        row_4.addWidget(self.overlap, 1)
        row_4.addStretch(1)

        row_5 = QHBoxLayout()
        row_5.addWidget(self.order)
        row_5.addWidget(self.relative_to)

        self._grid_img = GridRendering()

        layout = QVBoxLayout(self)
        layout.addWidget(self._grid_img)
        layout.addLayout(row_1)
        layout.addLayout(row_2)
        layout.addLayout(row_3)
        layout.addLayout(row_4)
        layout.addLayout(row_5)
        layout.addStretch()

        self.top.valueChanged.connect(self._on_change)
        self.bottom.valueChanged.connect(self._on_change)
        self.left.valueChanged.connect(self._on_change)
        self.right.valueChanged.connect(self._on_change)
        self.rows.valueChanged.connect(self._on_change)
        self.columns.valueChanged.connect(self._on_change)
        self.area_width.valueChanged.connect(self._on_change)
        self.area_height.valueChanged.connect(self._on_change)
        self.overlap.valueChanged.connect(self._on_change)
        self.order.currentIndexChanged.connect(self._on_change)
        self.relative_to.currentIndexChanged.connect(self._on_change)

        self.setMode(Mode.NUMBER)

    def _on_change(self) -> None:
        val = self.value()
        draw_grid = val.replace(relative_to="top_left")
        if isinstance(val, useq.GridRelative):
            draw_grid.fov_height = 1 / ((val.rows - 1) or 1)
            draw_grid.fov_width = 1 / ((val.columns - 1) or 1)
        if isinstance(val, useq.GridFromEdges):
            draw_grid.fov_height = 1 / (val.bottom - val.top)
            draw_grid.fov_width = 1 / (val.right - val.left)
        self._grid_img.grid = draw_grid
        self._grid_img.update()

    def mode(self) -> Mode:
        return self._mode

    def setMode(self, mode: Mode | str | None = None) -> None:
        btn = None
        if isinstance(mode, QRadioButton):
            btn = cast("QRadioButton", mode)
        elif mode is None:  # use sender if mode is None
            sender = cast("QButtonGroup", self.sender())
            btn = sender.checkedButton()
        if btn is not None:
            _mode: dict[QRadioButton, Mode] = {
                self._mode_number_radio: Mode.NUMBER,
                self._mode_area_radio: Mode.AREA,
                self._mode_bounds_radio: Mode.BOUNDS,
            }.get(btn)
        else:
            _mode = Mode(mode)  # type: ignore

        self._mode = _mode
        mode_groups: dict[Mode, Sequence[QWidget]] = {
            Mode.NUMBER: (self.rows, self.columns),
            Mode.AREA: (self.area_width, self.area_height),
            Mode.BOUNDS: (self.left, self.top, self.right, self.bottom),
        }
        for group, members in mode_groups.items():
            for member in members:
                member.setEnabled(_mode == group)

    def value(self) -> useq.GridFromEdges | useq.GridRelative:
        over = self.overlap.value() / 100
        common = {"overlap": (over, over), "mode": self.order.currentEnum().value}
        if self._mode == Mode.NUMBER:
            return useq.GridRelative(
                rows=self.rows.value(),
                columns=self.columns.value(),
                relative_to=self.relative_to.currentEnum().value,
                **common,
            )
        else:
            return useq.GridFromEdges(
                top=0,
                left=0,
                bottom=self.area_height.value(),
                right=self.area_width.value(),
            )


class GridRendering(QWidget):
    def __init__(self, grid: useq.AnyGridPlan | None = None, line_width=2):
        super().__init__()
        self.grid = grid
        self.line_width = line_width

    def paintEvent(self, e: QPaintEvent | None) -> None:
        if not self.grid:
            return
        painter = QPainter(self)
        pen = QPen(Qt.GlobalColor.black, self.line_width, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        super().paintEvent(e)
        # Calculate the actual positions from normalized indices
        w, h = self.width(), self.height()

        points = [QPoint(int(w * p.x), -int(h * p.y)) for p in self.grid]

        if len(points) < 2:
            return
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])

    def sizeHint(self) -> QSize:
        return QSize(200, 200)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = ImageGrid()
    w.show()
    sys.exit(app.exec_())
