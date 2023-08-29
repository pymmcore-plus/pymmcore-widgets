from enum import Enum
from typing import Sequence, cast

import useq
from qtpy.QtCore import QPoint, QSize, Qt, Signal
from qtpy.QtGui import QPainter, QPaintEvent, QPen, QResizeEvent
from qtpy.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QEnumComboBox
from superqt.utils import signals_blocked


class RelativeTo(Enum):
    center = "center"
    top_left = "top_left"


class OrderMode(Enum):
    """Different ways of ordering the grid positions."""

    row_wise_snake = "row_wise_snake"
    column_wise_snake = "column_wise_snake"
    spiral = "spiral"
    row_wise = "row_wise"
    column_wise = "column_wise"


class Mode(Enum):
    NUMBER = "number"
    AREA = "area"
    BOUNDS = "bounds"


class GridPlanWidget(QWidget):
    valueChanged = Signal(object)

    _mode: Mode

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._fov_width: float | None = None
        self._fov_height: float | None = None

        self.rows = QSpinBox()
        self.rows.setRange(1, 1000)
        self.rows.setValue(1)
        self.rows.setSuffix(" fields")
        self.columns = QSpinBox()
        self.columns.setRange(1, 1000)
        self.columns.setValue(1)
        self.columns.setSuffix(" fields")

        self.area_width = QDoubleSpinBox()
        self.area_width.setRange(0.01, 100)
        self.area_width.setDecimals(2)
        self.area_width.setSuffix(" mm")
        self.area_width.setSingleStep(0.1)
        self.area_height = QDoubleSpinBox()
        self.area_height.setRange(0.01, 100)
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

        row_col_layout = QHBoxLayout()
        row_col_layout.addWidget(self._mode_number_radio)
        row_col_layout.addWidget(QLabel("Rows:"))
        row_col_layout.addWidget(self.rows, 1)
        row_col_layout.addWidget(QLabel("Cols:"))
        row_col_layout.addWidget(self.columns, 1)

        width_height_layout = QHBoxLayout()
        width_height_layout.addWidget(self._mode_area_radio)
        width_height_layout.addWidget(QLabel("Width:"))
        width_height_layout.addWidget(self.area_width, 1)
        width_height_layout.addWidget(QLabel("Height:"))
        width_height_layout.addWidget(self.area_height, 1)

        lrtb_grid = QGridLayout()
        lrtb_grid.addWidget(QLabel("Left:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        lrtb_grid.addWidget(self.left, 0, 1)
        lrtb_grid.addWidget(QLabel("Top:"), 0, 2, Qt.AlignmentFlag.AlignRight)
        lrtb_grid.addWidget(self.top, 0, 3)
        lrtb_grid.addWidget(QLabel("Right:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        lrtb_grid.addWidget(self.right, 1, 1)
        lrtb_grid.addWidget(QLabel("Bottom:"), 1, 2, Qt.AlignmentFlag.AlignRight)
        lrtb_grid.addWidget(self.bottom, 1, 3)
        lrtb_grid.setColumnStretch(1, 1)
        lrtb_grid.setColumnStretch(3, 1)

        bounds_layout = QHBoxLayout()
        bounds_layout.addWidget(self._mode_bounds_radio)
        bounds_layout.addLayout(lrtb_grid, 1)

        bottom_stuff = QHBoxLayout()

        bot_left = QFormLayout()
        bot_left.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        bot_left.addRow("Overlap:", self.overlap)
        bot_left.addRow("Order:", self.order)
        bot_left.addRow("Relative to:", self.relative_to)

        self._grid_img = _GridRendering()
        bottom_stuff.addLayout(bot_left)
        bottom_stuff.addWidget(self._grid_img, 1, Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addLayout(row_col_layout)
        layout.addWidget(_SeparatorWidget())
        layout.addLayout(width_height_layout)  # hiding until useq supports it
        layout.addWidget(_SeparatorWidget())
        layout.addLayout(bounds_layout)
        layout.addWidget(_SeparatorWidget())
        layout.addLayout(bottom_stuff)
        layout.addStretch()

        self.setMode(Mode.NUMBER)

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

    def _on_change(self) -> None:
        val = self.value()

        if val is not None:  # temporary
            draw_grid = val.replace(relative_to="top_left")
            if isinstance(val, useq.GridRowsColumns):
                draw_grid.fov_height = 1 / ((val.rows - 1) or 1)
                draw_grid.fov_width = 1 / ((val.columns - 1) or 1)
            if isinstance(val, useq.GridFromEdges):
                draw_grid.fov_height = 1 / ((val.bottom - val.top) or 1)
                draw_grid.fov_width = 1 / ((val.right - val.left) or 1)
            self._grid_img.grid = draw_grid
            self._grid_img.update()

            self.valueChanged.emit(val)

    def mode(self) -> Mode:
        return self._mode

    def setMode(self, mode: Mode | str | None = None) -> None:
        btn = None
        btn_map: dict[QAbstractButton, Mode] = {
            self._mode_number_radio: Mode.NUMBER,
            self._mode_area_radio: Mode.AREA,
            self._mode_bounds_radio: Mode.BOUNDS,
        }
        if isinstance(mode, QRadioButton):
            btn = cast("QRadioButton", mode)
        elif mode is None:  # use sender if mode is None
            sender = cast("QButtonGroup", self.sender())
            btn = sender.checkedButton()
        if btn is not None:
            _mode: Mode = btn_map[btn]
        else:
            _mode = Mode(mode)
            {v: k for k, v in btn_map.items()}[_mode].setChecked(True)

        previous, self._mode = getattr(self, "_mode", None), _mode
        if previous != self._mode:
            mode_groups: dict[Mode, Sequence[QWidget]] = {
                Mode.NUMBER: (self.rows, self.columns),
                Mode.AREA: (self.area_width, self.area_height),
                Mode.BOUNDS: (self.left, self.top, self.right, self.bottom),
            }
            for group, members in mode_groups.items():
                for member in members:
                    member.setEnabled(_mode == group)

            self._on_change()

    def value(self) -> useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight:
        over = self.overlap.value() / 100
        _order = cast("OrderMode", self.order.currentEnum())
        common = {
            "overlap": (over, over),
            "mode": _order.value,
            "fov_width": self._fov_width,
            "fov_height": self._fov_height,
        }
        if self._mode == Mode.NUMBER:
            return useq.GridRowsColumns(
                rows=self.rows.value(),
                columns=self.columns.value(),
                relative_to=cast("RelativeTo", self.relative_to.currentEnum()).value,
                **common,
            )
        elif self._mode == Mode.BOUNDS:
            return useq.GridFromEdges(
                top=self.top.value(),
                left=self.left.value(),
                bottom=self.bottom.value(),
                right=self.right.value(),
                **common,
            )
        elif self._mode == Mode.AREA:
            return useq.GridWidthHeight(
                width=self.area_width.value(),
                height=self.area_height.value(),
                relative_to=cast("RelativeTo", self.relative_to.currentEnum()).value,
                **common,
            )
        raise NotImplementedError

    def setValue(self, value: useq.GridFromEdges | useq.GridRowsColumns) -> None:
        with signals_blocked(self):
            if isinstance(value, useq.GridRowsColumns):
                self.rows.setValue(value.rows)
                self.columns.setValue(value.columns)
                self.relative_to.setCurrentText(value.relative_to.value)
            elif isinstance(value, useq.GridFromEdges):
                self.top.setValue(value.top)
                self.left.setValue(value.left)
                self.bottom.setValue(value.bottom)
                self.right.setValue(value.right)
            elif isinstance(value, useq.GridWidthHeight):
                self.area_width.setValue(value.width)
                self.area_height.setValue(value.height)
                self.relative_to.setCurrentText(value.relative_to.value)
            else:
                raise TypeError(f"Expected useq grid plan, got {type(value)}")

            if value.fov_height:
                self._fov_height = value.fov_height
            if value.fov_width:
                self._fov_width = value.fov_width

        self._on_change()

    def setFovWidth(self, value: float) -> None:
        self._fov_width = value
        self._on_change()

    def setFovHeight(self, value: float) -> None:
        self._fov_height = value
        self._on_change()

    def fovWidth(self) -> float:
        return self._fov_width

    def fovHeight(self) -> float:
        return self._fov_height


class _SeparatorWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.gray, 1, Qt.PenStyle.SolidLine))
        painter.drawLine(self.rect().topLeft(), self.rect().topRight())


class _GridRendering(QWidget):
    def __init__(self, grid: useq.AnyGridPlan | None = None, line_width: int = 1):
        super().__init__()
        self.grid = grid
        self.line_width = line_width

    def paintEvent(self, e: QPaintEvent | None) -> None:
        if not self.grid:
            return

        # Calculate the actual positions from normalized indices
        fraction = 0.8  # fraction of the widget to use
        w, h = self.width(), self.height()
        half_w = w * (1 - fraction) / 2
        half_h = h * (1 - fraction) / 2
        points = [
            QPoint(int(w * p.x * fraction + half_w), -int(h * p.y * fraction - half_h))
            for p in self.grid
        ]

        if len(points) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        line_pen = QPen(Qt.GlobalColor.black, self.line_width, Qt.PenStyle.SolidLine)
        point_pen = QPen(Qt.GlobalColor.red, self.line_width, Qt.PenStyle.SolidLine)

        for i in range(len(points) - 1):
            painter.setPen(line_pen)
            painter.drawLine(points[i], points[i + 1])
            painter.setPen(point_pen)
            painter.drawEllipse(points[i], self.line_width + 2, self.line_width + 2)
        painter.drawEllipse(points[-1], self.line_width + 2, self.line_width + 2)

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        if not event:
            return
        size = event.size()
        new_width = size.width()
        new_height = size.height()

        if new_width / new_height > 1:
            new_width = int(new_height * 1)
        else:
            new_height = int(new_width / 1)

        self.resize(new_width, new_height)

    def sizeHint(self) -> QSize:
        return QSize(95, 95)
