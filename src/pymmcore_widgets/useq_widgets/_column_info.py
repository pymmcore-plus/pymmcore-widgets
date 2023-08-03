from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, ClassVar, Generic, NamedTuple, TypeVar, cast

import pint
from qtpy.QtCore import Qt
from qtpy.QtGui import QValidator
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

if TYPE_CHECKING:
    from typing import Any


@dataclass(frozen=True)
class ColumnInfo:
    # role used to store ColumnMeta in header items
    _ROLE: ClassVar[int] = Qt.ItemDataRole.UserRole + 1

    key: str
    data_type: type | WdgGetSet
    header: str | None = None
    is_row_selector: bool = False
    hidden: bool = False
    default: Any = None

    def header_text(self) -> str:
        return self.header or self.key.title().replace("_", " ")

    def init_cell(self, table: QTableWidget, row: int, col: int) -> None:
        raise NotImplementedError("Must be implemented by subclass")

    def get_cell_data(self, table: QTableWidget, row: int, col: int) -> dict[str, Any]:
        raise NotImplementedError("Must be implemented by subclass")

    def set_cell_data(
        self, table: QTableWidget, row: int, col: int, value: Any
    ) -> None:
        raise NotImplementedError("Must be implemented by subclass")


CHECKABLE_FLAGS = (
    Qt.ItemFlag.ItemIsUserCheckable
    | Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsEditable
    | Qt.ItemFlag.ItemIsSelectable
)


@dataclass(frozen=True)
class TextColumn(ColumnInfo):
    """Column that will use a standard QTableWidgetItem."""

    key: str
    data_type: type = str
    header: str | None = None
    is_row_selector: bool = False
    hidden: bool = False
    default: str | None = None
    checkable: bool = False
    checked: bool = True

    def init_cell(self, table: QTableWidget, row: int, col: int) -> None:
        # make a new QTableWidgetItem with the default value
        default = self.default.format(idx=row + 1) if self.default else ""
        item = QTableWidgetItem(default)

        if self.is_row_selector or self.checkable:
            ch = Qt.CheckState.Checked if self.checked else Qt.CheckState.Unchecked
            item.setFlags(CHECKABLE_FLAGS)
            # note: it's important to call setCheckState either way
            # otherwise the checkbox will not be visible
            item.setCheckState(ch)

        table.setItem(row, col, item)

    def get_cell_data(self, table: QTableWidget, row: int, col: int) -> dict[str, Any]:
        if item := table.item(row, col):
            return {self.key: item.text()}
        return {}


T = TypeVar("T")
W = TypeVar("W", bound=QWidget)


class WdgGetSet(NamedTuple, Generic[W, T]):
    widget: type[W]
    getter: Callable[[W], T]
    setter: Callable[[W, T], None]
    connect: Callable[[W, Callable[[T], None]], Any]


@dataclass(frozen=True)
class WidgetColumn(ColumnInfo, Generic[W, T]):
    key: str
    data_type: WdgGetSet[W, T]
    header: str | None = None
    is_row_selector: bool = False
    hidden: bool = False

    def _init_widget(self) -> W:
        return self.data_type.widget()
        # if self.choices and hasattr(new_wdg, "addItems"):
        #     new_wdg.addItems(self.choices)

    def init_cell(self, table: QTableWidget, row: int, col: int) -> None:
        new_wdg = self._init_widget()

        if self.default is not None:
            self.data_type.setter(new_wdg, self.default)

        #     new_wdg.setMaximum(self.maximum)
        # if self.alignment and hasattr(new_wdg, "setAlignment"):
        #     new_wdg.setAlignment(self.alignment)

        # header = cast("QHeaderView", self.table.horizontalHeader())
        # header.setSectionResizeMode(col, column_info.resize_mode)
        table.setCellWidget(row, col, new_wdg)

    def get_cell_data(self, table: QTableWidget, row: int, col: int) -> dict[str, Any]:
        if wdg := table.cellWidget(row, col):
            return {self.key: self.data_type.getter(cast(W, wdg))}
        return {}


# ############################# Booleans ################################


class _CenteredCheckBox(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._checkbox = QCheckBox()
        layout.addWidget(self._checkbox)

    def isChecked(self) -> bool:
        return self._checkbox.isChecked()

    def setChecked(self, value: bool) -> None:
        self._checkbox.setChecked(value)


TableBoolWidget = WdgGetSet(
    _CenteredCheckBox,
    _CenteredCheckBox.isChecked,
    _CenteredCheckBox.setChecked,
    lambda w, cb: w._checkbox.toggled.connect(cb),
)


@dataclass(frozen=True)
class BoolColumn(WidgetColumn):
    data_type: WdgGetSet = TableBoolWidget


# ############################# NUMBERS ################################


class _TableSpinboxMixin:
    def __init__(self: QDoubleSpinBox | QSpinBox) -> None:
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setKeyboardTracking(False)
        self.setMinimumWidth(70)
        self.setStyleSheet("QAbstractSpinBox { border: none; }")

    def wheelEvent(self, event: Any) -> None:
        # disable mouse wheel scrolling on table spinboxes
        pass  # pragma: no cover


class TableSpinBox(QSpinBox, _TableSpinboxMixin):
    pass


class TableDoubleSpinBox(QDoubleSpinBox, _TableSpinboxMixin):
    pass


TableIntWidget = WdgGetSet(
    TableSpinBox,
    QSpinBox.value,
    QSpinBox.setValue,
    lambda w, cb: w.valueChanged.connect(cb),
)


TableFloatWidget = WdgGetSet(
    TableDoubleSpinBox,
    QDoubleSpinBox.value,
    QDoubleSpinBox.setValue,
    lambda w, cb: w.valueChanged.connect(cb),
)


@dataclass(frozen=True)
class _RangeColumn(WidgetColumn, Generic[W, T]):
    data_type: WdgGetSet[W, float]
    minimum: float = 0
    maximum: float = 10_000

    def _init_widget(self) -> W:
        wdg = self.data_type.widget()

        if self.minimum is not None and hasattr(wdg, "setMinimum"):
            wdg.setMinimum(self.minimum)
        if self.maximum is not None and hasattr(wdg, "setMaximum"):
            wdg.setMaximum(self.maximum)

        return wdg


@dataclass(frozen=True)
class IntColumn(_RangeColumn):
    data_type: WdgGetSet = TableIntWidget
    minimum: int = 0
    maximum: int = 10_000


@dataclass(frozen=True)
class FloatColumn(_RangeColumn):
    data_type: WdgGetSet = TableFloatWidget


# ########################  Timepoints  ################################


class QQuantityValidator(QValidator):
    def __init__(
        self,
        dimensionality: str | None = None,
        ureg: pint.UnitRegistry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.dimensionality = dimensionality
        self.ureg = ureg or pint.application_registry

    def validate(self, a0: str | None, a1: int) -> tuple[QValidator.State, str, int]:
        if self.is_valid(a0):
            return (QValidator.State.Acceptable, a0 or "", a1)
        return (QValidator.State.Intermediate, a0 or "", a1)

    def is_valid(self, text: str | None) -> bool:
        if not text:
            return False
        try:
            q = self.ureg.parse_expression(text)
            if self.dimensionality:
                return isinstance(q, pint.Quantity) and bool(
                    q.is_compatible_with(self.dimensionality)
                )
            return True
        except pint.UndefinedUnitError:
            return False


class QQuantityLineEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._validator = QQuantityValidator(parent=self)
        self.setValidator(self._validator)
        self._last_valid: str = self.text()
        self.editingFinished.connect(self._on_editing_finished)

    def setDimensionality(self, dimensionality: str | None) -> None:
        self._validator.dimensionality = dimensionality

    def setUreg(self, ureg: pint.UnitRegistry) -> None:
        if not isinstance(ureg, pint.UnitRegistry):
            raise TypeError(f"ureg must be a pint.UnitRegistry, not {type(ureg)}")
        self._validator.ureg = ureg

    def focusOutEvent(self, event: Any) -> None:
        # When the widget loses focus, check if the text is valid
        self._on_editing_finished()
        super().focusOutEvent(event)

    def setText(self, value: str | None) -> None:
        if not self._validator.is_valid(value):
            raise ValueError(f"Invalid value: {value!r}")
        super().setText(value)
        self._last_valid = cast(str, value)

    def _on_editing_finished(self) -> None:
        # When the editing is finished, check if the final text is valid
        final_text = self.text()
        if self._validator.is_valid(final_text):
            self._last_valid = final_text
            self.setText(f"{self.quantity():~P}")  # short pretty format
        else:
            self.setText(self._last_valid)

    def quantity(self) -> pint.Quantity:
        return self._validator.ureg.parse_expression(self.text())


class QTimeLineEdit(QQuantityLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDimensionality("second")
        self.setStyleSheet("QLineEdit { border: none; }")

    def value(self) -> float:
        return self.quantity().to("second").magnitude  # type: ignore

    def setValue(self, value: float) -> None:
        self.setText(str(value))


TableTimeWidget = WdgGetSet(
    QTimeLineEdit,
    QTimeLineEdit.value,
    QTimeLineEdit.setValue,
    lambda w, cb: w.editingFinished.connect(cb),
)


@dataclass(frozen=True)
class TimeDeltaColumn(WidgetColumn):
    data_type: WdgGetSet = TableTimeWidget
