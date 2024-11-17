from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import Qt, Signal
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

if TYPE_CHECKING:
    from typing import Literal, TypeAlias

    GridPlan: TypeAlias = (
        useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight
    )


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

    def __str__(self) -> str:
        return self.value

    def to_useq_cls(self) -> type[GridPlan]:
        return _MODE_TO_USEQ[self]

    @classmethod
    def for_grid_plan(cls, plan: GridPlan) -> Mode:
        if isinstance(plan, useq.GridRowsColumns):
            return cls.NUMBER
        elif isinstance(plan, useq.GridFromEdges):
            return cls.BOUNDS
        elif isinstance(plan, useq.GridWidthHeight):
            return cls.AREA
        raise TypeError(f"Unknown grid plan type: {type(plan)}")  # pragma: no cover


_MODE_TO_USEQ: dict[Mode, type[GridPlan]] = {
    Mode.NUMBER: useq.GridRowsColumns,
    Mode.BOUNDS: useq.GridFromEdges,
    Mode.AREA: useq.GridWidthHeight,
}


class GridPlanWidget(QScrollArea):
    """Widget to edit a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans)."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mode: Mode = Mode.AREA  # will change to NUMBER below in init
        self._fov_width: float | None = None
        self._fov_height: float | None = None

        # WIDGETS -----------------------------------------------

        # Radio buttons to select the mode
        self._mode_number_radio = QRadioButton("Fields of View")
        self._mode_area_radio = QRadioButton("Width && Height")
        self._mode_bounds_radio = QRadioButton("Absolute Bounds")
        # group the radio buttons together
        self._mode_btn_group = QButtonGroup()
        self._mode_btn_group.addButton(self._mode_number_radio)
        self._mode_btn_group.addButton(self._mode_area_radio)
        self._mode_btn_group.addButton(self._mode_bounds_radio)
        self._mode_btn_group.buttonToggled.connect(self.setMode)

        self.row_col_wdg = _RowsColsWidget()
        self.width_height_wdg = _WidthHeightWidget()
        self.bounds_wdg = _BoundsWidget()
        # ease of lookup
        self._mode_to_widget: dict[
            Mode, _RowsColsWidget | _WidthHeightWidget | _BoundsWidget
        ] = {
            Mode.NUMBER: self.row_col_wdg,
            Mode.AREA: self.width_height_wdg,
            Mode.BOUNDS: self.bounds_wdg,
        }

        self._bottom_stuff = _BottomStuff()
        # aliases
        self.overlap = self._bottom_stuff.overlap
        self.order = self._bottom_stuff.order
        self.relative_to = self._bottom_stuff.relative_to

        # LAYOUT -----------------------------------------------

        # radio buttons on the top row
        btns_row = QHBoxLayout()
        btns_row.addWidget(QLabel("Create Grid Using:"))
        btns_row.addWidget(self._mode_number_radio)
        btns_row.addWidget(self._mode_area_radio)
        btns_row.addWidget(self._mode_bounds_radio)

        # stack the different mode widgets on top of each other
        self._stack = _ResizableStackedWidget(self)
        self._stack.addWidget(self.row_col_wdg)
        self._stack.addWidget(self.width_height_wdg)
        self._stack.addWidget(self.bounds_wdg)

        # wrap the whole thing in an inner widget so we can put it in this ScrollArea
        inner_widget = QWidget(self)
        main_layout = QVBoxLayout(inner_widget)
        main_layout.addLayout(btns_row)
        main_layout.addWidget(SeparatorWidget())
        main_layout.addWidget(self._stack)
        main_layout.addWidget(self._bottom_stuff)
        main_layout.addStretch(1)

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

        # CONNECTIONS ------------------------------------------

        self.row_col_wdg.valueChanged.connect(self._on_change)
        self.width_height_wdg.valueChanged.connect(self._on_change)
        self.bounds_wdg.valueChanged.connect(self._on_change)
        self._bottom_stuff.valueChanged.connect(self._on_change)

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
        if isinstance(mode, QRadioButton):
            btn_map: dict[QAbstractButton, Mode] = {
                self._mode_number_radio: Mode.NUMBER,
                self._mode_area_radio: Mode.AREA,
                self._mode_bounds_radio: Mode.BOUNDS,
            }
            mode = btn_map[mode]
        elif isinstance(mode, str):
            mode = Mode(mode)

        previous, self._mode = getattr(self, "_mode", None), mode
        if previous != self._mode:
            current_wdg = self._mode_to_widget[self._mode]
            self._stack.setCurrentWidget(current_wdg)
            self._bottom_stuff.setMode(mode)
            self._on_change()

    def value(self) -> GridPlan:
        """Return the current value of the widget as a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans).

        Returns
        -------
        useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight
            The current [GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans)
            value of the widget.
        """
        kwargs = {
            **self._stack.currentWidget().value(),
            **self._bottom_stuff.value(),
            "fov_width": self._fov_width,
            "fov_height": self._fov_height,
        }
        if self._mode not in {Mode.NUMBER, Mode.AREA}:
            kwargs.pop("relative_to", None)
        return self._mode.to_useq_cls()(**kwargs)

    def setValue(self, value: GridPlan) -> None:
        """Set the current value of the widget from a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans).

        Parameters
        ----------
        value : useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight
            The [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans)
            to set.
        """
        mode = Mode.for_grid_plan(value)

        with signals_blocked(self):
            mode_wdg = self._mode_to_widget[mode]
            mode_wdg.setValue(value)  # type: ignore [arg-type]
            self._stack.setCurrentWidget(mode_wdg)
            if value.fov_height:
                self._fov_height = value.fov_height
            if value.fov_width:
                self._fov_width = value.fov_width
            with signals_blocked(self._bottom_stuff):
                self._bottom_stuff.setValue(value)
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
        layout.setContentsMargins(12, 12, 12, 4)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addRow("Grid Rows:", self.rows)
        layout.addRow("Grid Cols:", self.columns)

        self.rows.valueChanged.connect(self.valueChanged)
        self.columns.valueChanged.connect(self.valueChanged)

    def value(self) -> dict[str, int]:
        return {"rows": self.rows.value(), "columns": self.columns.value()}

    def setValue(self, plan: useq.GridRowsColumns) -> None:
        self.rows.setValue(plan.rows)
        self.columns.setValue(plan.columns)


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
        layout.setContentsMargins(12, 12, 12, 4)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addRow("Width:", self.area_width)
        layout.addRow("Height:", self.area_height)

        self.area_width.valueChanged.connect(self.valueChanged)
        self.area_height.valueChanged.connect(self.valueChanged)

    def value(self) -> dict[str, float]:
        # converting width and height to microns because GridWidthHeight expects µm
        return {
            "width": self.area_width.value() * 1000,
            "height": self.area_height.value() * 1000,
        }

    def setValue(self, plan: useq.GridWidthHeight) -> None:
        # GridWidthHeight width and height are expressed in µm but this widget
        # uses mm, so we convert width and height to mm here
        self.area_width.setValue(plan.width / 1000)
        self.area_height.setValue(plan.height / 1000)


class _BoundsWidget(QWidget):
    valueChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.left = QDoubleSpinBox()
        self.left.setRange(-10000, 10000)
        self.left.setDecimals(3)
        self.top = QDoubleSpinBox()
        self.top.setRange(-10000, 10000)
        self.top.setDecimals(3)
        self.right = QDoubleSpinBox()
        self.right.setRange(-10000, 10000)
        self.right.setDecimals(3)
        self.bottom = QDoubleSpinBox()
        self.bottom.setRange(-10000, 10000)
        self.bottom.setDecimals(3)

        form = QFormLayout(self)
        form.setContentsMargins(12, 12, 12, 4)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Left:", self.left)
        form.addRow("Top:", self.top)
        form.addRow("Right:", self.right)
        form.addRow("Bottom:", self.bottom)

        self.top.valueChanged.connect(self.valueChanged)
        self.bottom.valueChanged.connect(self.valueChanged)
        self.left.valueChanged.connect(self.valueChanged)
        self.right.valueChanged.connect(self.valueChanged)

    def value(self) -> dict[str, float]:
        return {
            "left": self.left.value(),
            "top": self.top.value(),
            "right": self.right.value(),
            "bottom": self.bottom.value(),
        }

    def setValue(self, plan: useq.GridFromEdges) -> None:
        self.left.setValue(plan.left)
        self.top.setValue(plan.top)
        self.right.setValue(plan.right)
        self.bottom.setValue(plan.bottom)


class _ResizableStackedWidget(QStackedWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.currentChanged.connect(self.onCurrentChanged)

    def addWidget(self, wdg: QWidget | None) -> int:
        if wdg is not None:
            wdg.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        return super().addWidget(wdg)  # type: ignore [no-any-return]

    def onCurrentChanged(self, idx: int) -> None:
        for i in range(self.count()):
            plc = QSizePolicy.Policy.Minimum if i == idx else QSizePolicy.Policy.Ignored
            if wdg := self.widget(i):
                wdg.setSizePolicy(plc, plc)
                wdg.adjustSize()
        self.adjustSize()


class _BottomStuff(QWidget):
    valueChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.overlap = QDoubleSpinBox()
        self.overlap.setRange(-1000, 1000)
        self.overlap.setValue(0)
        self.overlap.setSuffix(" %")
        self.order = QEnumComboBox(self, OrderMode)
        self.relative_to = QEnumComboBox(self, RelativeTo)

        self._form_layout = QFormLayout(self)
        self._form_layout.setContentsMargins(12, 0, 12, 12)
        self._form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self._form_layout.addRow("", SeparatorWidget())
        self._form_layout.addRow("Overlap:", self.overlap)
        self._form_layout.addRow("Acquisition order:", self.order)
        self._form_layout.addRow("Current position:", self.relative_to)

        self.overlap.valueChanged.connect(self.valueChanged)
        self.order.currentIndexChanged.connect(self.valueChanged)
        self.relative_to.currentIndexChanged.connect(self.valueChanged)

    def setMode(self, mode: Mode) -> None:
        vis = mode != Mode.BOUNDS
        for role in (QFormLayout.ItemRole.LabelRole, QFormLayout.ItemRole.FieldRole):
            self._form_layout.itemAt(3, role).widget().setVisible(vis)

    def value(self) -> dict:
        return {
            "overlap": (self.overlap.value(), self.overlap.value()),
            "mode": self.order.currentEnum().value,
            "relative_to": self.relative_to.currentEnum().value,
        }

    def setValue(self, plan: GridPlan) -> None:
        if plan.overlap:
            self.overlap.setValue(plan.overlap[0])
        if hasattr(plan, "relative_to"):
            self.relative_to.setCurrentText(plan.relative_to.value)
        self.order.setCurrentEnum(OrderMode(plan.mode.value))
