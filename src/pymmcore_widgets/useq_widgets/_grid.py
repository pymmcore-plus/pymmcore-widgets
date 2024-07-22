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
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
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

        self.stack = _ResizableStackedWidget(self)
        self._row_col_wdg = _RowsColsWidget()
        self.stack.addWidget(self._row_col_wdg)
        self._width_height_wdg = _WidthHeightWidget()
        self.stack.addWidget(self._width_height_wdg)
        self._bounds_wdg = _BoundsWidget()
        self.stack.addWidget(self._bounds_wdg)

        self._bottom_stuff = _BottomStuff()

        # wrap the whole thing in an inner widget so we can put it in this ScrollArea
        inner_widget = QWidget(self)
        layout = QVBoxLayout(inner_widget)
        layout.addLayout(top_layout)
        layout.addWidget(SeparatorWidget())
        layout.addWidget(self.stack)
        layout.addWidget(self._bottom_stuff)
        layout.addStretch()

        self.setWidget(inner_widget)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._mode_number_radio.setChecked(True)

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

        self._bottom_stuff.setMode(mode)

    def value(self) -> useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight:
        """Return the current value of the widget as a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans).

        Returns
        -------
        useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight
            The current [GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans)
            value of the widget.
        """
        over = self._bottom_stuff.overlap.value()
        order = self._bottom_stuff.order.currentEnum()
        common = {
            "overlap": (over, over),
            "mode": order.value,
            "fov_width": self._fov_width,
            "fov_height": self._fov_height,
        }

        if self._mode == Mode.NUMBER:
            return useq.GridRowsColumns(
                rows=self._row_col_wdg.rows.value(),
                columns=self._row_col_wdg.columns.value(),
                relative_to=self._bottom_stuff.relative_to.currentEnum().value,
                **common,
            )
        elif self._mode == Mode.BOUNDS:
            return useq.GridFromEdges(
                top=self._bounds_wdg.top.value(),
                left=self._bounds_wdg.left.value(),
                bottom=self._bounds_wdg.bottom.value(),
                right=self._bounds_wdg.right.value(),
                **common,
            )
        elif self._mode == Mode.AREA:
            # converting width and height to microns because GridWidthHeight expects µm
            return useq.GridWidthHeight(
                width=self._width_height_wdg.area_width.value() * 1000,
                height=self._width_height_wdg.area_height.value() * 1000,
                relative_to=self._bottom_stuff.relative_to.currentEnum().value,
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
                self._row_col_wdg.rows.setValue(value.rows)
                self._row_col_wdg.columns.setValue(value.columns)
                self._bottom_stuff.relative_to.setCurrentText(value.relative_to.value)
            elif isinstance(value, useq.GridFromEdges):
                self._bounds_wdg.top.setValue(value.top)
                self._bounds_wdg.left.setValue(value.left)
                self._bounds_wdg.bottom.setValue(value.bottom)
                self._bounds_wdg.right.setValue(value.right)
            elif isinstance(value, useq.GridWidthHeight):
                # GridWidthHeight width and height are expressed in µm but this widget
                # uses mm, so we convert width and height to mm here
                self._width_height_wdg.area_width.setValue(value.width / 1000)
                self._width_height_wdg.area_height.setValue(value.height / 1000)
                self._bottom_stuff.relative_to.setCurrentText(value.relative_to.value)
            else:  # pragma: no cover
                raise TypeError(f"Expected useq grid plan, got {type(value)}")

            if value.fov_height:
                self._fov_height = value.fov_height
            if value.fov_width:
                self._fov_width = value.fov_width

            if value.overlap:
                self._bottom_stuff.overlap.setValue(value.overlap[0])

            self._bottom_stuff.order.setCurrentEnum(OrderMode(value.mode.value))

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


class _RowsColsWidget(QWidget):
    valueChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.rows = QSpinBox()
        self.rows.setRange(1, 1000)
        self.rows.setValue(1)
        self.rows.setSuffix(" fields")
        self.columns = QSpinBox()
        self.columns.setRange(1, 1000)
        self.columns.setValue(1)
        self.columns.setSuffix(" fields")

        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addRow("Grid Rows:", self.rows)
        layout.addRow("Grid Cols:", self.columns)

        self.rows.valueChanged.connect(self.valueChanged)
        self.columns.valueChanged.connect(self.valueChanged)


class _WidthHeightWidget(QWidget):
    valueChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

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

        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addRow("Width:", self.area_width)
        layout.addRow("Height:", self.area_height)

        self.area_width.valueChanged.connect(self.valueChanged)
        self.area_height.valueChanged.connect(self.valueChanged)


class _BoundsWidget(QWidget):
    valueChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

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

        self.lrtb_wdg = QWidget()
        lrtb_layout = QFormLayout(self.lrtb_wdg)
        lrtb_layout.setContentsMargins(12, 0, 12, 12)
        lrtb_layout.addRow("Left:", self.left)
        lrtb_layout.addRow("Top:", self.top)
        lrtb_layout.addRow("Right:", self.right)
        lrtb_layout.addRow("Bottom:", self.bottom)

        self.bounds_layout = QFormLayout(self)
        self.bounds_layout.addWidget(self.lrtb_wdg)

        self.top.valueChanged.connect(self.valueChanged)
        self.bottom.valueChanged.connect(self.valueChanged)
        self.left.valueChanged.connect(self.valueChanged)
        self.right.valueChanged.connect(self.valueChanged)


class _ResizableStackedWidget(QStackedWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.currentChanged.connect(self.onCurrentChanged)

    def addWidget(self, wdg: QWidget | None) -> int:
        if wdg is not None:
            wdg.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        return super().addWidget(wdg)  # type: ignore

    def onCurrentChanged(self, idx: int) -> None:
        for i in range(self.count()):
            wdg = self.widget(i)
            if wdg is None:
                continue
            if i == idx:
                wdg.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
                )
            else:
                wdg.setSizePolicy(
                    QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
                )
            wdg.adjustSize()
        self.adjustSize()


class _BottomStuff(QWidget):
    valueChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.overlap_lbl = QLabel("Overlap:")
        self.overlap = QDoubleSpinBox()
        self.overlap.setRange(-1000, 1000)
        self.overlap.setValue(0)
        self.overlap.setSuffix(" %")
        self.order_lbl = QLabel("Acquisition order:")
        self.order = QEnumComboBox(self, OrderMode)
        self.relative_to_lbl = QLabel("Current position:")
        self.relative_to = QEnumComboBox(self, RelativeTo)

        self.form_layout = QFormLayout(self)
        self.form_layout.setContentsMargins(12, 0, 12, 12)
        self.form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.form_layout.addRow("", SeparatorWidget())
        # NB relative_to added in self.setMode
        self.form_layout.addRow(self.overlap_lbl, self.overlap)
        self.form_layout.addRow(self.order_lbl, self.order)

        self.overlap.valueChanged.connect(self.valueChanged)
        self.order.currentIndexChanged.connect(self.valueChanged)
        self.relative_to.currentIndexChanged.connect(self.valueChanged)

    def setMode(self, mode: Mode) -> None:
        if mode == Mode.BOUNDS:
            self.relative_to.hide()
            self.relative_to_lbl.hide()
            self.form_layout.removeWidget(self.relative_to_lbl)
            self.form_layout.removeWidget(self.relative_to)
        else:
            self.relative_to.show()
            self.relative_to_lbl.show()
            self.form_layout.addRow(self.relative_to_lbl, self.relative_to)
