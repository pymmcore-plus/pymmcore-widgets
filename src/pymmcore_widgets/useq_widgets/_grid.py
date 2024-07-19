from __future__ import annotations

from enum import Enum
from typing import Literal

import useq
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from superqt import QEnumComboBox
from superqt.utils import signals_blocked

from pymmcore_widgets._util import SeparatorWidget


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
    NUMBER = "Fields of View"
    AREA = "Width & Height"
    BOUNDS = "Absolute Bounds"

    def __str__(self) -> str:
        return self.value


class GridPlanWidget(QScrollArea):
    """Widget to edit a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans)."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mode: Mode = Mode.AREA  # will change to NUMBER below in init
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
        # here for area_width and area_height we are using mm instead of µm because
        # (as in GridWidthHeight) because it is probably easier for a user to define
        # the area in mm
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

        self.overlap = 0.0
        self.overlaps: list[QDoubleSpinBox] = []
        self.order = OrderMode.row_wise
        self.orders: list[QEnumComboBox] = []
        self.relative_to = RelativeTo.center
        self.relative_tos: list[QEnumComboBox] = []

        def _add_overlap_widget(layout: QFormLayout) -> None:
            overlap = QDoubleSpinBox()
            overlap.setRange(-1000, 1000)
            overlap.setValue(0)
            overlap.setSuffix(" %")

            def on_change(val: float) -> None:
                self.overlap = val
                for o in self.overlaps:
                    o.setValue(val)

            self.overlaps.append(overlap)
            overlap.valueChanged.connect(on_change)
            layout.addRow("Overlap:", overlap)

        def _add_order_widget(layout: QFormLayout) -> None:
            combo = QEnumComboBox(self, OrderMode)
            combo.currentEnum()

            def on_change(enum: OrderMode) -> None:
                self.order = enum
                for o in self.orders:
                    o.setCurrentEnum(enum)

            combo.currentEnumChanged.connect(on_change)
            self.orders.append(combo)
            layout.addRow("Order:", combo)

        def _add_relative_to_widget(layout: QFormLayout) -> None:
            combo = QEnumComboBox(self, RelativeTo)
            combo.currentEnum()

            def on_change(enum: RelativeTo) -> None:
                self.relative_to = enum
                for o in self.relative_tos:
                    o.setCurrentEnum(enum)

            self.relative_tos.append(combo)
            combo.currentEnumChanged.connect(on_change)
            combo.setToolTip("The current stage position within the larger grid")
            layout.addRow("Current Position:", combo)

        self._mode_number_radio = QRadioButton()
        self._mode_number_radio.setText("Fields of View")
        self._mode_area_radio = QRadioButton()
        self._mode_area_radio.setText("Width && Height")
        self._mode_bounds_radio = QRadioButton()
        self._mode_bounds_radio.setText("Absolute Bounds")
        self._mode_btn_group = QButtonGroup()
        self._mode_btn_group.addButton(self._mode_number_radio)
        self._mode_btn_group.addButton(self._mode_area_radio)
        self._mode_btn_group.addButton(self._mode_bounds_radio)
        self._mode_btn_group.buttonToggled.connect(self.setMode)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Create Grid Using:"))
        top_layout.addWidget(self._mode_number_radio)
        top_layout.addWidget(self._mode_area_radio)
        top_layout.addWidget(self._mode_bounds_radio)

        row_col_layout = QFormLayout()
        row_col_layout.addRow("Grid Rows:", self.rows)
        row_col_layout.addRow("Grid Cols:", self.columns)
        row_col_layout.addWidget(SeparatorWidget())
        _add_overlap_widget(row_col_layout)
        _add_order_widget(row_col_layout)
        _add_relative_to_widget(row_col_layout)

        width_height_layout = QFormLayout()
        width_height_layout.addRow("Width:", self.area_width)
        width_height_layout.addRow("Height:", self.area_height)
        width_height_layout.addWidget(SeparatorWidget())
        _add_overlap_widget(width_height_layout)
        _add_order_widget(width_height_layout)
        _add_relative_to_widget(width_height_layout)

        self.lrtb_wdg = QWidget()
        lrtb_grid = QGridLayout(self.lrtb_wdg)
        lrtb_grid.setContentsMargins(0, 0, 0, 0)
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

        self.bounds_layout = QFormLayout()
        self.bounds_layout.addWidget(self.lrtb_wdg)
        self.bounds_layout.addWidget(SeparatorWidget())
        _add_overlap_widget(self.bounds_layout)
        _add_order_widget(self.bounds_layout)

        # wrap the whole thing in an inner widget so we can put it in this ScrollArea
        inner_widget = QWidget(self)
        layout = QVBoxLayout(inner_widget)
        layout.addLayout(top_layout)
        layout.addWidget(SeparatorWidget())
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack)
        layout.addStretch()

        wdg_num = QWidget(self.stack)
        wdg_num.setLayout(row_col_layout)
        self.stack.addWidget(wdg_num)
        wdg_area = QWidget(self.stack)
        wdg_area.setLayout(width_height_layout)
        self.stack.addWidget(wdg_area)
        wdg_bounds = QWidget(self.stack)
        wdg_bounds.setLayout(self.bounds_layout)
        self.stack.addWidget(wdg_bounds)

        self.setWidget(inner_widget)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._mode_number_radio.setChecked(True)

        self.top.valueChanged.connect(self._on_change)
        self.bottom.valueChanged.connect(self._on_change)
        self.left.valueChanged.connect(self._on_change)
        self.right.valueChanged.connect(self._on_change)
        self.rows.valueChanged.connect(self._on_change)
        self.columns.valueChanged.connect(self._on_change)
        self.area_width.valueChanged.connect(self._on_change)
        self.area_height.valueChanged.connect(self._on_change)
        for o in self.overlaps:
            o.valueChanged.connect(self._on_change)
        for o in self.orders:
            o.currentIndexChanged.connect(self._on_change)
        for r in self.relative_tos:
            r.currentIndexChanged.connect(self._on_change)

        # FIXME: On Windows 11, buttons within an inner widget of a ScrollArea
        # are filled in with the accent color, making it very difficult to see
        # which radio button is checked. This HACK solves the issue. It's
        # likely future Qt versions will fix this.
        inner_widget.setStyleSheet("QRadioButton {color: none}")

    # ------------------------- Public API -------------------------

    def mode(self) -> Mode:
        """Return the current mode, one of "number", "area", or "bounds"."""
        return self._mode

    def setMode(self, mode: Mode | Literal["number", "area", "bounds"]) -> None:
        """Set the current mode, one of "number", "area", or "bounds".

        Parameters
        ----------
        mode : Mode | Literal["number", "area", "bounds"]
            The mode to set.
        """
        btn_map: dict[QAbstractButton, Mode] = {
            self._mode_number_radio: Mode.NUMBER,
            self._mode_area_radio: Mode.AREA,
            self._mode_bounds_radio: Mode.BOUNDS,
        }
        if isinstance(mode, str):
            mode = Mode(mode)
        elif isinstance(mode, QRadioButton):
            mode = btn_map[mode]

        previous, self._mode = getattr(self, "_mode", None), mode
        if previous != self._mode:
            for i, m in enumerate(Mode):
                if mode == m:
                    self.stack.setCurrentIndex(i)
            self._on_change()

    def value(self) -> useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight:
        """Return the current value of the widget as a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans).

        Returns
        -------
        useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight
            The current [GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans)
            value of the widget.
        """
        common = {
            "overlap": (self.overlap, self.overlap),
            "mode": self.order.value,
            "fov_width": self._fov_width,
            "fov_height": self._fov_height,
        }

        if self._mode == Mode.NUMBER:
            return useq.GridRowsColumns(
                rows=self.rows.value(),
                columns=self.columns.value(),
                relative_to=self.relative_to.value,
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
            # converting width and height to microns because GridWidthHeight expects µm
            return useq.GridWidthHeight(
                width=self.area_width.value() * 1000,
                height=self.area_height.value() * 1000,
                relative_to=self.relative_to.value,
                **common,
            )
        raise NotImplementedError

    def setValue(self, value: useq.GridFromEdges | useq.GridRowsColumns) -> None:
        """Set the current value of the widget from a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans).

        Parameters
        ----------
        value : useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight
            The [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans)
            to set.
        """
        with signals_blocked(self):
            if isinstance(value, useq.GridRowsColumns):
                self.rows.setValue(value.rows)
                self.columns.setValue(value.columns)
                for r in self.relative_tos:
                    r.setCurrentText(value.relative_to.value)
            elif isinstance(value, useq.GridFromEdges):
                self.top.setValue(value.top)
                self.left.setValue(value.left)
                self.bottom.setValue(value.bottom)
                self.right.setValue(value.right)
            elif isinstance(value, useq.GridWidthHeight):
                # GridWidthHeight width and height are expressed in µm but this widget
                # uses mm, so we convert width and height to mm here
                self.area_width.setValue(value.width / 1000)
                self.area_height.setValue(value.height / 1000)
                for r in self.relative_tos:
                    r.setCurrentText(value.relative_to.value)
            else:  # pragma: no cover
                raise TypeError(f"Expected useq grid plan, got {type(value)}")

            if value.fov_height:
                self._fov_height = value.fov_height
            if value.fov_width:
                self._fov_width = value.fov_width

            if value.overlap:
                for o in self.overlaps:
                    o.setValue(value.overlap[0])

            for o in self.orders:
                o.setCurrentEnum(OrderMode(value.mode.value))

            mode = {
                useq.GridRowsColumns: Mode.NUMBER,
                useq.GridFromEdges: Mode.BOUNDS,
                useq.GridWidthHeight: Mode.AREA,
            }[type(value)]
            self.setMode(mode)

        self._on_change()

    def setFovWidth(self, value: float) -> None:
        """Set the current field of view width."""
        self._fov_width = value
        self._on_change()

    def setFovHeight(self, value: float) -> None:
        """Set the current field of view height."""
        self._fov_height = value
        self._on_change()

    def fovWidth(self) -> float | None:
        """Return the current field of view width."""
        return self._fov_width

    def fovHeight(self) -> float | None:
        """Return the current field of view height."""
        return self._fov_height

    # ------------------------- Private API -------------------------

    def sizeHint(self) -> QSize:
        """Return the size hint for the viewport."""
        sz = super().sizeHint()
        sz.setHeight(200)  # encourage vertical scrolling
        return sz

    def _on_change(self) -> None:
        if (val := self.value()) is None:
            return  # pragma: no cover
        self.valueChanged.emit(val)
